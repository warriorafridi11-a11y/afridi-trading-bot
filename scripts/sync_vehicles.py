"""Daily sync for Afridi Trading Bot vehicles.

Easy words: this script reads the real car list from afriditrading.com,
then updates the Supabase cars table so the bot always knows the true
stock. It adds cars that are new, updates the price if a car changed,
and marks cars that are gone from the website as "sold" (it never
deletes a row, so old cars stay in the history).

How it works:
- It fetches the stock pages with plain HTTP (no browser needed).
- Each car has a reference like AA35371 from its page link. That
  reference is the match key. Cars without a reference are matched
  by make + model + year + price instead.
- It only marks cars as "sold" on a FULL crawl (all pages). On a
  short crawl it skips that step, because a car on page 50 would
  look "gone" by mistake.
- The bot keeps its own short cache (5 minutes), so new data shows
  up in the bot soon after this sync runs. The sync time is printed
  at the end, so you can see when it last ran.

Setup (never put keys in this file):
  SUPABASE_URL=https://jlbapnqzntqlyjuqvtmq.supabase.co
  SUPABASE_ANON_KEY=<the anon key from Supabase Dashboard > Settings > API>

Run it:
  python3 scripts/sync_vehicles.py                 (first 10 pages)
  python3 scripts/sync_vehicles.py --max-pages 0   (all pages = full sync)
  python3 scripts/sync_vehicles.py --dry-run       (look only, change nothing)
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SITE = "https://www.afriditrading.com/cars"
PER_PAGE = 24

# One car card on the stock page looks like this in the HTML:
#   <a href="/car-detail/AA35371">2021 Suzuki Solio MV</a>
#   <p ...specs">33,000 km · 1200cc · AT · Hybrid</p>
#   <span ...priceMain">$10,550</span>
CARD_RE = re.compile(
    r'href="/car-detail/([A-Za-z0-9]+)">(\d{4})\s+([^<]+)</a>'
    r'.*?<p[^>]*__specs">([^<]*)</p>'
    r'.*?<span[^>]*__priceMain">\$([\d,]+)</span>',
    re.DOTALL,
)
KM_RE = re.compile(r"([\d,]+)\s*km")


def fetch_page(page):
    """Fetch one stock page and return its HTML text."""
    url = f"{SITE}?page={page}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "AfridiTradingBot-Sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_cars(html):
    """Turn one page of HTML into a list of car dicts."""
    cars = []
    for ref, year, title, specs, price in CARD_RE.findall(html):
        title = title.strip()
        make, _, model = title.partition(" ")
        km = KM_RE.search(specs)
        fuel = ""
        if "Hybrid" in specs:
            fuel = "Hybrid"
        elif "Light Oil" in specs:
            fuel = "Light Oil"
        cars.append({
            "ref": ref,
            "make": make,
            "model": model.strip(),
            "year": int(year),
            "distance_km": int(km.group(1).replace(",", "")) if km else None,
            "price_fob": int(price.replace(",", "")),
            "body_type": fuel,  # the listing shows fuel, not body type
            "status": "In stock",
        })
    return cars


def crawl(max_pages):
    """Fetch stock pages. max_pages 0 means all pages."""
    cars, page = [], 1
    while True:
        if max_pages and page > max_pages:
            break
        try:
            found = parse_cars(fetch_page(page))
        except Exception as exc:  # noqa: BLE001 - one bad page ends the crawl
            print(f"STOP: page {page} could not be read: {exc}")
            break
        if not found:
            break
        cars.extend(found)
        print(f"Page {page}: {len(found)} cars")
        page += 1
    return cars


# ---------- Supabase (plain REST, no extra package) ----------

def sb_request(method, path, data=None):
    """One call to the Supabase REST API. Returns the parsed JSON."""
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1" + path
    key = os.environ["SUPABASE_ANON_KEY"]
    req = urllib.request.Request(url, method=method)
    req.add_header("apikey", key)
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    if data is not None:
        req.add_header("Prefer", "return=representation")
        body = json.dumps(data).encode()
    else:
        body = None
    try:
        with urllib.request.urlopen(req, data=body, timeout=30) as resp:
            text = resp.read().decode()
            return json.loads(text) if text else []
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="ignore")[:300]
        raise RuntimeError(f"Supabase {method} {path} failed "
                           f"({exc.code}): {detail}")


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--max-pages", type=int, default=10,
                      help="How many stock pages to read. 0 = all pages.")
    args.add_argument("--dry-run", action="store_true",
                      help="Look only, change nothing in Supabase.")
    opts = args.parse_args()

    print(f"SYNC START: {datetime.now(timezone.utc).isoformat()}")
    cars = crawl(opts.max_pages)
    print(f"Found {len(cars)} cars on the website.")
    if opts.dry_run:
        for car in cars[:5]:
            print("  sample:", car)
        print("DRY RUN: nothing was changed in Supabase.")
        print("SUMMARY: new=0 updated=0 marked sold=0 (dry run)")
        return 0

    if not os.environ.get("SUPABASE_URL") or \
            not os.environ.get("SUPABASE_ANON_KEY"):
        print("STOP: set SUPABASE_URL and SUPABASE_ANON_KEY first. "
              "They are never stored in this file.")
        return 1

    # The cars table needs a ref column for safe matching. If it is
    # missing, the seed SQL (supabase seed file) must be run first.
    try:
        sb_request("GET", "/cars?select=ref&limit=1")
    except RuntimeError as exc:
        if "ref" in str(exc):
            print("STOP: the Supabase cars table has no 'ref' column "
                  "yet. Run the seed SQL file first, then run this again.")
            return 1
        raise

    existing = sb_request(
        "GET", "/cars?select=id,ref,make,model,year,distance_km,"
        "price_fob,body_type,status&limit=10000")

    def key(car):
        if car.get("ref"):
            return ("ref", car["ref"])
        return ("fields", car["make"], car["model"], car["year"],
                car["price_fob"])

    have = {key(c): c for c in existing}
    seen, new, updated = set(), 0, 0
    for car in cars:
        k = key(car)
        seen.add(k)
        old = have.get(k)
        if old is None:
            sb_request("POST", "/cars", car)
            new += 1
        else:
            changes = {}
            for field in ("distance_km", "price_fob", "body_type"):
                if car[field] != old.get(field):
                    changes[field] = car[field]
            if old.get("status") in ("sold", "Sold"):
                changes["status"] = "In stock"
            if not old.get("ref") and car.get("ref"):
                changes["ref"] = car["ref"]
            if changes:
                sb_request("PATCH", f"/cars?id=eq.{old['id']}", changes)
                updated += 1

    # Only a full crawl can say a car is really gone.
    sold = 0
    if opts.max_pages == 0:
        for k, old in have.items():
            if k not in seen and old.get("status") != "sold":
                sb_request("PATCH", f"/cars?id=eq.{old['id']}",
                           {"status": "sold"})
                sold += 1
    else:
        print("NOTE: short crawl, so no car was marked sold. "
              "Use --max-pages 0 for a full sync.")

    print(f"SYNC TIME: {datetime.now(timezone.utc).isoformat()}")
    print(f"SUMMARY: new={new} updated={updated} marked sold={sold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
