"""Crawl queue for the Afridi Trading Bot.

Easy words: the website has about 38,000 cars on about 1,600 pages.
If we ask for them all at once, the website blocks us (error 429).
So this script works slowly, like a queue at a shop: one page at a
time, a short wait between pages, and it remembers which pages are
done. Each run takes only a few pages. Run it again and again (once
a day, by a schedule) and the bot slowly gets all the cars.

How it works:
- The queue is a small table called crawl_queue in the same SQLite
  database file as the bot (bot.db). Same table and column names will
  be used in Supabase later, so moving is easy.
- `python3 scripts/crawl_queue.py --fill` reads page 1 of the website,
  counts how many cars there are, and adds one queue row for every
  stock page (page 1, 2, 3, ...). Pages already in the queue are
  skipped, so filling twice is safe.
- `python3 scripts/crawl_queue.py --pages 10` takes the next 10
  pages from the queue, waits 3 seconds between pages (polite, so
  the website does not block us), and saves every car it finds.
  New cars are added to the cars table AND to the seed list in
  seed_data.py, so the live bot gets them on the next deploy.
- If a page fails (for example error 429 = "too many requests"),
  that page is marked failed, the run STOPS at once, and the page
  stays in the queue to try again next time. After 3 failed tries
  a page is left alone for a human to look at.
- Cars that disappear from the website are NOT marked sold here.
  Only a full sync (scripts/sync_vehicles.py --max-pages 0) does
  that, because only a full crawl can say a car is really gone.

This worker runs on a schedule (once a day), NOT on Vercel.
On Vercel the bot only reads the cars; it never crawls.

Run it:
  python3 scripts/crawl_queue.py --fill
  python3 scripts/crawl_queue.py --pages 10
  python3 scripts/crawl_queue.py --pages 5 --delay 5
  python3 scripts/crawl_queue.py --status
"""

import argparse
import math
import os
import re
import sqlite3
import sys
import time
import urllib.error
from datetime import datetime, timezone

# The crawler helpers (fetch_page, parse_cars) live in the sync
# script next to this file. Importing it is safe: it only runs its
# own main() when started directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_vehicles import fetch_page, parse_cars  # noqa: E402

SITE = "https://www.afriditrading.com/cars"
PER_PAGE = 24  # the website shows 24 cars on one stock page
MAX_ATTEMPTS = 3  # after 3 failed tries, leave the page for a human
DEFAULT_DELAY = 3  # seconds to wait between pages (be polite)
DEFAULT_PAGES = 10  # pages to crawl in one run

# If the website does not say how many cars it has, use the count
# we saw on 2026-11-20. The --fill step reads the live count first.
FALLBACK_TOTAL_CARS = 38236

TOTAL_RE = re.compile(r"of\s+([\d,]+)\s+cars")

QUEUE_SQL = """
CREATE TABLE IF NOT EXISTS crawl_queue (
    id INTEGER PRIMARY KEY,
    page_url TEXT,
    page_number INTEGER UNIQUE,
    status TEXT,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TEXT,
    done_at TEXT
);
"""

CARS_SQL = """
CREATE TABLE IF NOT EXISTS cars (
    id INTEGER PRIMARY KEY, make TEXT, model TEXT, year INTEGER,
    distance_km INTEGER, price_fob INTEGER, body_type TEXT,
    status TEXT, ref TEXT, auction_grade TEXT, image_url TEXT,
    condition_note TEXT
);
"""


def now_text():
    """Current time as text, for the database."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_db(db_path):
    """Open the bot database and make sure the tables exist."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.executescript(QUEUE_SQL + CARS_SQL)
    # Old database files may miss the new columns: add them.
    cols = [r[1] for r in db.execute("PRAGMA table_info(cars)")]
    for col in ("auction_grade", "image_url", "condition_note"):
        if col not in cols:
            db.execute(f"ALTER TABLE cars ADD COLUMN {col} TEXT")
    db.commit()
    return db


def total_cars_on_site():
    """Read page 1 and count how many cars the website says it has."""
    html = fetch_page(1)
    found = TOTAL_RE.search(html)
    if not found:
        return FALLBACK_TOTAL_CARS
    return int(found.group(1).replace(",", ""))


def fill_queue(db, already_done=0):
    """Add one queue row for every stock page. Safe to run twice."""
    total = total_cars_on_site()
    pages = math.ceil(total / PER_PAGE)
    added = 0
    for number in range(1, pages + 1):
        status = "done" if number <= already_done else "pending"
        done_at = now_text() if number <= already_done else None
        cur = db.execute(
            "INSERT OR IGNORE INTO crawl_queue"
            " (page_url, page_number, status, attempts, created_at,"
            " done_at) VALUES (?, ?, ?, 0, ?, ?)",
            (f"{SITE}?page={number}", number, status, now_text(), done_at))
        added += cur.rowcount
    db.commit()
    print(f"Website has {total} cars on {pages} pages.")
    print(f"Queue: {added} new pages added.")
    return pages


def queue_status(db):
    """Print how the queue is doing, and return the counts."""
    rows = db.execute(
        "SELECT status, COUNT(*) AS n FROM crawl_queue"
        " GROUP BY status").fetchall()
    counts = {r["status"]: r["n"] for r in rows}
    total = sum(counts.values())
    print(f"Queue: {total} pages — "
          f"{counts.get('pending', 0)} pending, "
          f"{counts.get('doing', 0)} doing, "
          f"{counts.get('done', 0)} done, "
          f"{counts.get('failed', 0)} failed.")
    nxt = db.execute(
        "SELECT MIN(page_number) FROM crawl_queue"
        " WHERE status = 'pending'").fetchone()[0]
    if nxt:
        print(f"Next page to crawl: {nxt}.")
    return counts


def seed_key(car):
    """Match a car in the seed list: make, model, year, km, price."""
    return (car["make"], car["model"], car["year"],
            car["distance_km"], car["price_fob"])


def load_seed_keys(seed_py):
    """Read the cars already in the seed_data.py seed list."""
    keys = set()
    try:
        with open(seed_py, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return keys
    start = text.find("SAMPLE_CARS = [")
    if start < 0:
        return keys
    end = text.find("\n]\n", start)
    block = text[start:end] if end > 0 else text[start:]
    for line in block.splitlines():
        line = line.strip().strip(",").strip('"')
        parts = line.split("|")
        if len(parts) >= 7:
            try:
                keys.add((parts[0], parts[1], int(parts[2]),
                          int(parts[3]) if parts[3] else None,
                          int(parts[4])))
            except ValueError:
                continue
    return keys


def append_to_seed(seed_py, cars):
    """Add new cars to the SAMPLE_CARS list in seed_data.py, so
    the live bot gets them on the next deploy. New lines carry
    the ref, auction grade and photo link too. Returns how many
    were added."""
    keys = load_seed_keys(seed_py)
    new_lines = []
    for car in cars:
        if seed_key(car) in keys:
            continue
        km = "" if car["distance_km"] is None else str(car["distance_km"])
        grade = car.get("auction_grade") or ""
        image = car.get("image_url") or ""
        ref = car.get("ref") or ""
        new_lines.append(
            f'    "{car["make"]}|{car["model"]}|{car["year"]}|{km}|'
            f'{car["price_fob"]}|{car["body_type"]}|{car["status"]}|'
            f'{ref}|{grade}|{image}",')
        keys.add(seed_key(car))
    if not new_lines:
        return 0
    with open(seed_py, encoding="utf-8") as handle:
        text = handle.read()
    start = text.find("SAMPLE_CARS = [")
    end = text.find("\n]\n", start)
    if start < 0 or end < 0:
        print("WARNING: could not find SAMPLE_CARS in seed_data.py, so"
              " the new cars were saved in the database only.")
        return 0
    text = text[:end] + "\n" + "\n".join(new_lines) + text[end:]
    with open(seed_py, "w", encoding="utf-8") as handle:
        handle.write(text)
    return len(new_lines)


def upsert_cars(db, cars):
    """Add new cars to the database, update changed ones.
    Match by the website reference (e.g. AA35371), or by make +
    model + year + price when there is no reference."""
    new, updated = 0, 0
    for car in cars:
        old = None
        if car.get("ref"):
            old = db.execute(
                "SELECT * FROM cars WHERE ref = ?",
                (car["ref"],)).fetchone()
        if old is None:
            old = db.execute(
                "SELECT * FROM cars WHERE make = ? AND model = ?"
                " AND year = ? AND price_fob = ?",
                (car["make"], car["model"], car["year"],
                 car["price_fob"])).fetchone()
        if old is None:
            db.execute(
                "INSERT INTO cars (make, model, year, distance_km,"
                " price_fob, body_type, status, ref, auction_grade,"
                " image_url, condition_note)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (car["make"], car["model"], car["year"],
                 car["distance_km"], car["price_fob"],
                 car["body_type"], car["status"], car.get("ref"),
                 car.get("auction_grade"), car.get("image_url"),
                 car.get("condition_note")))
            new += 1
        else:
            changes = {}
            for field in ("distance_km", "price_fob", "body_type",
                          "auction_grade", "image_url", "condition_note"):
                if car.get(field) != old[field]:
                    # Never wipe a grade or photo already saved.
                    if field in ("auction_grade", "image_url",
                                 "condition_note") \
                            and car.get(field) is None:
                        continue
                    changes[field] = car[field]
            if old["status"] in ("sold", "Sold"):
                changes["status"] = "In stock"
            if not old["ref"] and car.get("ref"):
                changes["ref"] = car["ref"]
            if changes:
                sets = ", ".join(f"{k} = ?" for k in changes)
                db.execute(f"UPDATE cars SET {sets} WHERE id = ?",
                           (*changes.values(), old["id"]))
                updated += 1
    db.commit()
    return new, updated


def run_worker(db, seed_py, pages, delay, no_seed, fetch=None):
    """Crawl the next N pages from the queue. Stops at once if a
    page fails. Returns (done, added, updated, failed)."""
    fetch = fetch or fetch_page
    rows = db.execute(
        "SELECT * FROM crawl_queue WHERE status = 'pending'"
        " OR (status = 'failed' AND attempts < ?)"
        " ORDER BY page_number LIMIT ?",
        (MAX_ATTEMPTS, pages)).fetchall()
    done, added, updated, failed = 0, 0, 0, 0
    for row in rows:
        number = row["page_number"]
        if done > 0 or failed > 0:
            time.sleep(delay)
        db.execute("UPDATE crawl_queue SET status = 'doing'"
                   " WHERE id = ?", (row["id"],))
        db.commit()
        try:
            found = parse_cars(fetch(number))
            if not found:
                raise RuntimeError("page opened but no cars were found")
        except Exception as exc:  # noqa: BLE001 - any failure stops run
            db.execute(
                "UPDATE crawl_queue SET status = 'failed',"
                " attempts = attempts + 1, last_error = ? WHERE id = ?",
                (str(exc)[:300], row["id"]))
            db.commit()
            print(f"STOP: page {number} failed: {exc}")
            print("The run stops here. The page stays in the queue"
                  " to try again next time.")
            failed += 1
            break
        new, upd = upsert_cars(db, found)
        seeded = 0 if no_seed else append_to_seed(seed_py, found)
        db.execute(
            "UPDATE crawl_queue SET status = 'done', done_at = ?"
            " WHERE id = ?", (now_text(), row["id"]))
        db.commit()
        done += 1
        added += new
        updated += upd
        print(f"Page {number}: {len(found)} cars, {new} new,"
              f" {upd} updated, {seeded} added to the seed list.")
    print(f"SUMMARY: pages done={done} cars added={added}"
          f" cars updated={updated} pages failed={failed}")
    return done, added, updated, failed


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--fill", action="store_true",
                      help="Add every stock page to the queue.")
    args.add_argument("--already-done", type=int, default=0,
                      help="On --fill, mark the first N pages done"
                      " (they were crawled before the queue existed).")
    args.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                      help="How many queue pages to crawl in one run.")
    args.add_argument("--delay", type=int, default=DEFAULT_DELAY,
                      help="Seconds to wait between pages.")
    args.add_argument("--no-seed", action="store_true",
                      help="Do not add new cars to the seed_data.py seed list.")
    args.add_argument("--status", action="store_true",
                      help="Show the queue status and stop.")
    args.add_argument("--db", default=None,
                      help="Database file (default: bot.db next to"
                      " the app).")
    opts = args.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    db_path = opts.db or os.path.join(repo, "bot.db")
    seed_py = os.path.join(repo, "seed_data.py")
    db = open_db(db_path)

    if opts.status:
        queue_status(db)
        return 0
    if opts.fill:
        fill_queue(db, already_done=opts.already_done)
        queue_status(db)
        return 0
    run_worker(db, seed_py, opts.pages, opts.delay, opts.no_seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
