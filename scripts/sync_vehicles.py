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
# The page also hides the full car data as JSON (NEXT_DATA), with
# the photo link, the auction grade and all the specs. The JSON is
# the better source: one car object has image, auction_grade,
# stock_id (the ref, e.g. AA35371), make, model, version (trim),
# manufacturing_year, mileage_km, fob_price_currency_to and fuel.
# The old HTML pattern below is only a fallback, for a day when
# the JSON is missing. Grades are rare on the site: most cars
# have no grade at all, so auction_grade stays empty (None) for
# them — the bot never invents a grade.
CARD_RE = re.compile(
    r'href="/car-detail/([A-Za-z0-9]+)">(\d{4})\s+([^<]+)</a>'
    r'.*?<p[^>]*__specs">([^<]*)</p>'
    r'.*?<span[^>]*__priceMain">\$([\d,]+)</span>',
    re.DOTALL,
)
KM_RE = re.compile(r"([\d,]+)\s*km")
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)

# Fuel words from the site, kept the same as the old seed data:
# the listing text says "Light Oil" for diesel cars.
FUEL_TAG = {"HYBRID": "Hybrid", "DIESEL": "Light Oil"}


def _title_make(raw):
    """Make name in the same shape as the old seed data."""
    name = raw.strip().title()
    if name == "Bmw":
        return "BMW"
    return name


def _model_name(raw_model, version):
    """Model + trim, like the listing title: 'Solio MV'."""
    model = raw_model.strip().title()
    trim = (version or "").strip()
    return f"{model} {trim}".strip() if trim else model


def fetch_page(page):
    """Fetch one stock page and return its HTML text."""
    url = f"{SITE}?page={page}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "AfridiTradingBot-Sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_cars(html):
    """Turn one page of HTML into a list of car dicts."""
    found = NEXT_DATA_RE.search(html)
    if found:
        try:
            data = json.loads(found.group(1))
            cars = []
            for item in data["props"]["pageProps"]["data"]:
                cars.append({
                    "ref": item.get("stock_id"),
                    "make": _title_make(item.get("make") or ""),
                    "model": _model_name(item.get("model") or "",
                                         item.get("version")),
                    "year": int(item.get("manufacturing_year") or 0),
                    "distance_km": item.get("mileage_km"),
                    "price_fob": int(item.get("fob_price_currency_to") or 0),
                    "body_type": FUEL_TAG.get(
                        (item.get("fuel") or "").upper(), ""),
                    "status": "In stock"
                    if (item.get("status") or "").upper() == "AVAILABLE"
                    else "In stock",
                    # Auction grade from the site, or None: most cars
                    # have no grade, and the bot never invents one.
                    "auction_grade": item.get("auction_grade") or None,
                    # Main photo of the car, from the site.
                    "image_url": item.get("image") or None,
                    # The site lists no condition note per car, so
                    # this stays empty unless the site adds one.
                    "condition_note": None,
                })
            if cars:
                return cars
        except Exception:  # noqa: BLE001 - fall back to the HTML pattern
            pass
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
            "auction_grade": None,
            "image_url": None,
            "condition_note": None,
        })
    return cars


def crawl(max_pages, start_page=1):
    """Fetch stock pages. max_pages 0 means all pages.
    Waits 3 seconds between pages, so the website does not block
    us. On error 429 (too many requests) the run stops at once."""
    import time
    cars, page = [], start_page
    while True:
        if max_pages and page > start_page + max_pages - 1:
            break
        try:
            found = parse_cars(fetch_page(page))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                print(f"STOP: page {page} got error 429 (too many "
                      "requests). The run stops here — try again later.")
            else:
                print(f"STOP: page {page} could not be read: {exc}")
            break
        except Exception as exc:  # noqa: BLE001 - one bad page ends the crawl
            print(f"STOP: page {page} could not be read: {exc}")
            break
        if not found:
            print(f"STOP: page {page} had no cars.")
            break
        cars.extend(found)
        grades = sum(1 for c in found if c.get("auction_grade"))
        photos = sum(1 for c in found if c.get("image_url"))
        print(f"Page {page}: {len(found)} cars, {grades} with a grade,"
              f" {photos} with a photo")
        page += 1
        if max_pages and page <= start_page + max_pages - 1:
            time.sleep(3)
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
    args.add_argument("--start-page", type=int, default=1,
                      help="First stock page to read (default 1).")
    args.add_argument("--out", default=None,
                      help="Also save the crawled cars to this JSON file.")
    args.add_argument("--dry-run", action="store_true",
                      help="Look only, change nothing in Supabase.")
    opts = args.parse_args()

    print(f"SYNC START: {datetime.now(timezone.utc).isoformat()}")
    cars = crawl(opts.max_pages, start_page=opts.start_page)
    print(f"Found {len(cars)} cars on the website.")
    if opts.out:
        with open(opts.out, "w", encoding="utf-8") as handle:
            json.dump(cars, handle, ensure_ascii=False)
        print(f"Saved {len(cars)} cars to {opts.out}.")
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
    # It also needs the auction_grade, image_url and condition_note
    # columns — see afridi-trading-bot-add-columns.sql.
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
        "price_fob,body_type,status,auction_grade,image_url,"
        "condition_note&limit=10000")

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
            for field in ("distance_km", "price_fob", "body_type",
                          "auction_grade", "image_url", "condition_note"):
                if car.get(field) != old.get(field):
                    # Never wipe a grade or photo the table already has.
                    if field in ("auction_grade", "image_url",
                                 "condition_note") and car.get(field) is None:
                        continue
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
