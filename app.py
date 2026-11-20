"""
Afridi Trading Bot — a simple chatbot for buying Japanese used cars.
Written in easy Python + Flask, in one file, so a student can explain it.
The bot is rule-based: it looks for keywords in the buyer's question
and answers from its knowledge base. No deep learning, no paid API.
"""

import os
import re
import sqlite3
import time
from datetime import datetime, timezone, timedelta

import smtplib
from email.message import EmailMessage

from flask import (Flask, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

# Supabase client. The import is guarded: if the supabase package
# is not installed, the bot simply uses SQLite (see USE_SUPABASE).
try:
    from supabase import create_client as _sb_create_client
except Exception:  # noqa: BLE001 - any import problem means no Supabase
    _sb_create_client = None

# QR codes for invoices. Guarded the same way: if the qrcode
# package is missing, invoices still work, just without a QR.
try:
    import qrcode
except Exception:  # noqa: BLE001 - any import problem means no QR
    qrcode = None

# The live site address. Every invoice QR encodes its own live
# invoice page, so a scan opens that exact invoice for checking.
LIVE_SITE = "https://afridi-trading-bot.vercel.app"

app = Flask(__name__)
# Secret key for sign-in sessions. On Vercel set SECRET_KEY in the
# project settings; the default below is only for local testing.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# The admin of this bot. When this email signs up or signs in, the
# account gets the SUPER_ADMIN role.
ADMIN_EMAIL = "warriorafridi11@gmail.com"

# The database is one small file. It is made by itself the first time.
# On Vercel the code folder is read-only, so the file goes in /tmp.
if os.environ.get("VERCEL"):
    DB_FILE = "/tmp/bot.db"
else:
    DB_FILE = os.path.join(os.path.dirname(__file__), "bot.db")

# ---------- Supabase (the real shared database) ----------
# When SUPABASE_URL and SUPABASE_ANON_KEY are set as environment
# variables (never in code, never in GitHub), the bot reads and
# writes Supabase instead of the local SQLite file. When they are
# not set, the bot uses SQLite, exactly as before. The anon key is
# a secret: it is only ever read from the environment.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_ANON_KEY
                    and _sb_create_client)
# The last Supabase problem, if the startup test failed (None = ok).
# Shown on /health so the admin can see why the bot is on SQLite.
_SUPABASE_ERROR = None

# The tables in Supabase, in the same names as the SQLite file.
# Used for the admin "tables" count (PostgREST cannot ask
# SQLite's sqlite_master table).
SUPABASE_TABLES = ["users", "admins", "cars", "chats", "messages",
                   "inquiries", "invoices", "shipments", "import_rules",
                   "reviews", "faqs", "crawl_queue"]

_sb_client = None


def _get_sb_client():
    """One shared Supabase client. Made once, reused after that."""
    global _sb_client
    if _sb_client is None:
        # httpx (used by supabase-py) cannot parse bracketed IPv6
        # addresses like [::1] in NO_PROXY, and fails with
        # "Invalid port". Drop those entries; plain hostnames stay.
        for name in ("NO_PROXY", "no_proxy"):
            value = os.environ.get(name)
            if value and "[" in value:
                os.environ[name] = ",".join(
                    p for p in value.split(",") if "[" not in p)
        _sb_client = _sb_create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _sb_client

# Simple shipping prices in US dollars, from Japan to each port.
# These are sample prices for the demo, not live quotes.
SHIPPING = {
    "jamaica": {"port": "Kingston, Jamaica", "price": 850},
    "trinidad and tobago": {"port": "Port of Spain, Trinidad", "price": 900},
    "trinidad": {"port": "Port of Spain, Trinidad", "price": 900},
    "ghana": {"port": "Tema, Ghana", "price": 1200},
    "kenya": {"port": "Mombasa, Kenya", "price": 1100},
    "antigua and barbuda": {"port": "St. John's, Antigua", "price": 950},
    "antigua": {"port": "St. John's, Antigua", "price": 950},
}

INSURANCE = 100  # simple marine insurance, in US dollars

# Auction grades, explained in simple words.
GRADES = {
    "s": "Grade S means the car is almost new. Very few marks, very low distance.",
    "5": "Grade 5 means the car is in very good shape. Almost no marks.",
    "4.5": "Grade 4.5 means the car is in very good shape. A few small marks only.",
    "4": "Grade 4 means the car is in good shape. Some small marks, but nothing big.",
    "3.5": "Grade 3.5 means the car is in fair shape. It has marks and small dents.",
    "3": "Grade 3 means the car has clear marks, dents or a repair. Read the sheet first.",
    "r": "Grade R means the car was repaired after an accident. Ask us before you buy it.",
}

# Make logos for the Cars page. Real logo pictures from carlogos.org.
# Only makes whose logo link was checked and works (HTTP 200) are
# listed here. A make not in this list shows its name in a text
# badge instead — never a broken picture.
MAKE_LOGOS = {
    "Toyota": "https://www.carlogos.org/car-logos/toyota-logo.png",
    "Honda": "https://www.carlogos.org/car-logos/honda-logo.png",
    "Lexus": "https://www.carlogos.org/car-logos/lexus-logo.png",
    "Mazda": "https://www.carlogos.org/car-logos/mazda-logo.png",
    "Nissan": "https://www.carlogos.org/car-logos/nissan-logo.png",
    "BMW": "https://www.carlogos.org/car-logos/bmw-logo.png",
    "Mercedes-Benz": "https://www.carlogos.org/car-logos/mercedes-benz-logo.png",
    "Suzuki": "https://www.carlogos.org/car-logos/suzuki-logo.png",
    "Mitsubishi": "https://www.carlogos.org/car-logos/mitsubishi-logo.png",
    "Audi": "https://www.carlogos.org/car-logos/audi-logo.png",
    "Daihatsu": "https://www.carlogos.org/car-logos/daihatsu-logo.png",
    "Subaru": "https://www.carlogos.org/car-logos/subaru-logo.png",
    "Ford": "https://www.carlogos.org/car-logos/ford-logo.png",
    "Hyundai": "https://www.carlogos.org/car-logos/hyundai-logo.png",
    "Volkswagen": "https://www.carlogos.org/car-logos/volkswagen-logo.png",
    "Volvo": "https://www.carlogos.org/car-logos/volvo-logo.png",
    "Porsche": "https://www.carlogos.org/car-logos/porsche-logo.png",
    "Land Rover": "https://www.carlogos.org/car-logos/land-rover-logo.png",
    "Peugeot": "https://www.carlogos.org/car-logos/peugeot-logo.png",
    "Maserati": "https://www.carlogos.org/car-logos/maserati-logo.png",
    "Kia": "https://www.carlogos.org/car-logos/kia-logo.png",
    "Skoda": "https://www.carlogos.org/car-logos/skoda-logo.png",
    "MG": "https://www.carlogos.org/car-logos/mg-logo.png",
    "Mg": "https://www.carlogos.org/car-logos/mg-logo.png",
    "Rover": "https://www.carlogos.org/car-logos/rover-logo.png",
    "Luxgen": "https://www.carlogos.org/car-logos/luxgen-logo.png",
}

# Seed data (cars, import rules, FAQs) lives in seed_data.py,
# only because app.py got too big to deploy in one piece.
from seed_data import SAMPLE_CARS, SAMPLE_FAQS, SAMPLE_RULES, \
    seed_car_rows





# ---------- simple cache ----------
# A plain Python dict with a 5-minute time limit. The bot reads the car
# list, the FAQs and the import rules again and again, so it keeps a copy
# in memory and only goes to the database when the copy is older than
# 5 minutes. No Redis, no extra service, no paid tool. The 5-minute limit
# is how the cache refreshes: new cars, FAQs or rules show up soon after
# they change. Hits and misses are counted for the /health page.
_CACHE = {}
_CACHE_TIME = {}
_CACHE_STATS = {"hits": 0, "misses": 0}
CACHE_SECONDS = 300  # 5 minutes


def cached_list(name, sql):
    """Get a table from the cache, or from the database if it is old."""
    now = time.time()
    if name in _CACHE and now - _CACHE_TIME[name] < CACHE_SECONDS:
        _CACHE_STATS["hits"] += 1
        return _CACHE[name]
    _CACHE_STATS["misses"] += 1
    db = get_db()
    rows = [dict(r) for r in db.execute(sql).fetchall()]
    _CACHE[name] = rows
    _CACHE_TIME[name] = now
    return rows


# ---------- sign-in helpers ----------

def role_for_email(email):
    """The admin email is SUPER_ADMIN. Everyone else is a buyer."""
    if email.strip().lower() == ADMIN_EMAIL:
        return "SUPER_ADMIN"
    return "buyer"


def current_user():
    """The signed-in user, or None for a guest."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?",
                      (user_id,)).fetchone()


def is_admin(user):
    """True only for the admin account."""
    return user is not None and user["role"] == "SUPER_ADMIN"


# ---------- database helpers ----------

# ---------- Supabase adapter ----------
# The rest of the app talks to the database through a tiny
# sqlite3-like link: db.execute(sql, params).fetchone()/fetchall()
# and db.commit(). These classes give Supabase the same shape, so
# no route or bot rule has to change. They only know the SQL this
# app actually uses; anything else raises a clear error.


class _Row(dict):
    """One database row. Like sqlite3.Row it works both ways:
    row["name"] and row[0] (the first column)."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _SupaCursor:
    """Holds the rows of one query. Like a sqlite3 cursor."""
    def __init__(self, rows):
        self._rows = [_Row(r) if isinstance(r, dict) else r for r in rows]

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


def _is_missing_table(exc):
    """True if a Supabase error says the table does not exist."""
    msg = str(exc)
    return "PGRST205" in msg or "Could not find the table" in msg


class SupaDB:
    """A small stand-in for a sqlite3 connection, backed by Supabase.
    Every call is saved at once, so commit() and close() do nothing."""
    def __init__(self, client):
        self.client = client

    def execute(self, sql, params=()):
        return _SupaCursor(self._run(sql, params or ()))

    def executemany(self, sql, rows):
        for row in rows:
            self.execute(sql, row)
        return _SupaCursor([])

    def commit(self):
        return None

    def close(self):
        return None

    def _run(self, sql, params):
        text = " ".join(sql.split())
        low = text.lower()
        if low == "select 1":
            return [{"1": 1}]
        if "sqlite_master" in low:
            return [{"count": len(SUPABASE_TABLES)}]
        try:
            if low.startswith("select"):
                return self._select(text, params)
            if low.startswith("insert"):
                return self._insert(text, params)
            if low.startswith("update"):
                return self._update(text, params)
            if low.startswith("delete"):
                return self._delete(text, params)
        except Exception as exc:
            # The crawl_queue table may not exist in Supabase yet.
            # Until it is made, the queue is simply empty.
            if "crawl_queue" in low and _is_missing_table(exc):
                return []
            raise
        raise ValueError("SQL not supported in Supabase mode: " + text[:80])

    def _select(self, text, params):
        # NOTE: the original text is parsed with case-insensitive
        # patterns, never lowercased — lowercasing would corrupt
        # string values like status 'Open'.
        # COUNT(*) — ask Supabase for the count only, not the rows.
        m = re.match(r"select count\(\*\) from (\w+)(?: where (.+))?$",
                     text, re.I)
        if m:
            q = self.client.table(m.group(1)).select(
                "id", count="exact").limit(1)
            if m.group(2):
                q = self._where(q, m.group(2), params)
            return [{"count": q.execute().count or 0}]
        if "left join" in text.lower():
            return self._join_select(text, params)
        if "group by" in text.lower():
            # Only used for the crawl queue: count rows by status.
            m = re.match(r"select (.+) from (\w+) group by (\w+)",
                         text, re.I)
            rows = _select_all(self.client, m.group(2), "*")
            counts = {}
            for r in rows:
                counts[r[m.group(3)]] = counts.get(r[m.group(3)], 0) + 1
            return [{"status": k, "n": v} for k, v in counts.items()]
        # Plain SELECT: cut off ORDER BY / LIMIT, then WHERE.
        order_col = order_desc = limit = None
        m = re.search(r"\border by (\w+)(?:\s+(asc|desc))?", text, re.I)
        if m:
            order_col = m.group(1)
            order_desc = (m.group(2) or "").lower() == "desc"
        m = re.search(r"\blimit (\d+)\s*$", text, re.I)
        if m:
            limit = int(m.group(1))
        head = re.split(r"\bwhere\b|\border by\b|\blimit\b", text,
                        flags=re.I)[0].strip()
        m = re.match(r"select (.+?) from (\w+)$", head, re.I)
        cols, table = m.group(1).strip(), m.group(2)
        where = None
        m = re.search(r"\bwhere\b(.+?)(?:\border by\b|\blimit\b|$)",
                      text, re.I)
        if m:
            where = m.group(1).strip()
        q = self.client.table(table).select(
            "*" if cols.lower() in ("*", "c.*", "i.*") else cols)
        if where:
            q = self._where(q, where, params)
        if order_col:
            q = q.order(order_col, desc=order_desc)
        if limit is not None:
            return q.limit(limit).execute().data
        # No LIMIT: fetch every row, 1000 at a time. PostgREST
        # returns at most 1000 rows in one call, so one call
        # would silently drop the rest of the cars. Order by id
        # too: without a unique order, rows with the same price
        # can appear twice or be skipped between pages.
        rows, start = [], 0
        q = q.order("id")
        while True:
            page = q.range(start, start + 999).execute().data
            rows.extend(page)
            if len(page) < 1000:
                break
            start += 1000
        return rows

    def _where(self, q, where, params):
        """Add WHERE parts to a Supabase query. Each ? uses the
        next value from params, in order."""
        i = 0
        for part in [p.strip() for p in
                     re.split(r"\s+and\s+", where, flags=re.I)]:
            m = re.match(r"lower\((\w+)\)\s*=\s*\?", part, re.I)
            if m:
                q = q.ilike(m.group(1), params[i])
                i += 1
                continue
            m = re.match(r"(\w+)\s*<=\s*\?", part)
            if m:
                q = q.lte(m.group(1), params[i])
                i += 1
                continue
            m = re.match(r"(\w+)\s*=\s*\?", part)
            if m:
                q = q.eq(m.group(1), params[i])
                i += 1
                continue
            m = re.match(r"(\w+)\s*=\s*'([^']*)'", part)
            if m:
                q = q.eq(m.group(1), m.group(2))
                continue
            if part.lower().startswith("substr(created_at"):
                # "Messages today": created_at is stored as an ISO
                # date-time string, so today means the date prefix.
                today = datetime.now(timezone.utc).date()
                tomorrow = today + timedelta(days=1)
                q = q.gte("created_at", today.isoformat())
                q = q.lt("created_at", tomorrow.isoformat())
                continue
            raise ValueError("WHERE not supported in Supabase mode: " + part)
        return q

    def _join_select(self, text, params):
        """The three JOIN queries: fetch both tables, join in Python."""
        low = text.lower()
        limit = None
        m = re.search(r"\blimit (\d+)\s*$", low)
        if m:
            limit = int(m.group(1))
        if "count(m.id)" in low:
            # My chats: each chat with how many messages it has.
            chats = _select_all(
                self.client, "chats", "*",
                self.client.table("chats").select("*").eq(
                    "user_id", params[0]).order("id", desc=True))
            if not chats:
                return []
            ids = [c["id"] for c in chats]
            msgs = _select_all(
                self.client, "messages", "chat_id",
                self.client.table("messages").select("chat_id").in_(
                    "chat_id", ids))
            counts = {}
            for msg in msgs:
                counts[msg["chat_id"]] = counts.get(msg["chat_id"], 0) + 1
            return [{**c, "messages": counts.get(c["id"], 0)}
                    for c in chats]
        if "from chats c" in low:
            # Admin: chats with the buyer's name.
            q = self.client.table("chats").select("*").order("id", desc=True)
            if limit is not None:
                q = q.limit(limit)
            chats = q.execute().data
            users = {u["id"]: u for u in _select_all(
                self.client, "users", "id,name")}
            return [{**c, "user_name": users.get(
                c.get("user_id"), {}).get("name")} for c in chats]
        if "from inquiries i" in low:
            # Admin: open questions with the buyer's name and email.
            rows = _select_all(
                self.client, "inquiries", "*",
                self.client.table("inquiries").select("*").eq(
                    "status", "open").order("id", desc=True))
            users = {u["id"]: u for u in _select_all(
                self.client, "users", "id,name,email")}
            return [{**r,
                     "user_name": users.get(
                         r.get("user_id"), {}).get("name"),
                     "user_email": users.get(
                         r.get("user_id"), {}).get("email")}
                    for r in rows]
        raise ValueError("JOIN not supported in Supabase mode: " + text[:80])

    @staticmethod
    def _split_values(text):
        """Split a VALUES list on commas, keeping quoted text whole."""
        parts, buf, in_quote = [], "", False
        for ch in text:
            if ch == "'":
                in_quote = not in_quote
                buf += ch
            elif ch == "," and not in_quote:
                parts.append(buf)
                buf = ""
            else:
                buf += ch
        parts.append(buf)
        return parts

    def _insert(self, text, params):
        m = re.match(r"insert into (\w+)\s*\(([^)]+)\)\s*values\s*\((.+)\)$",
                     text, re.I)
        cols = [c.strip() for c in m.group(2).split(",")]
        values, i = [], 0
        for tok in self._split_values(m.group(3)):
            tok = tok.strip()
            if tok == "?":
                values.append(params[i])
                i += 1
            elif tok.upper() == "NULL":
                values.append(None)
            elif tok.startswith("'") and tok.endswith("'"):
                values.append(tok[1:-1].replace("''", "'"))
            else:
                values.append(int(tok))
        row = dict(zip(cols, values))
        data = self.client.table(m.group(1)).insert(row).execute().data
        return data or [row]

    def _update(self, text, params):
        m = re.match(r"update (\w+) set (.+?) where (.+)$", text, re.I)
        vals, i = {}, 0
        for part in m.group(2).split(","):
            col, _, tok = part.strip().partition("=")
            tok = tok.strip()
            if tok == "?":
                vals[col.strip()] = params[i]
                i += 1
            elif tok.startswith("'"):
                vals[col.strip()] = tok[1:-1]
            else:
                vals[col.strip()] = tok
        m2 = re.match(r"(\w+)\s*=\s*\?", m.group(3).strip())
        q = self.client.table(m.group(1)).update(vals)
        if m2:
            q = q.eq(m2.group(1), params[i])
        return q.execute().data or []

    def _delete(self, text, params):
        m = re.match(r"delete from (\w+) where (\w+)\s*=\s*\?", text, re.I)
        self.client.table(m.group(1)).delete().eq(
            m.group(2), params[0]).execute()
        return []


def get_db():
    """One database link for this web request. Supabase when it is
    set up, otherwise the local SQLite file, as before."""
    if USE_SUPABASE:
        return SupaDB(_get_sb_client())
    if "db" not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    """Close the database link when the request ends."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _supabase_probe():
    """One tiny read to check Supabase really works: right key,
    right project, and the tables let the anon role read them.
    Returns None if it works, or the error text if not."""
    try:
        _get_sb_client().table("cars").select("id").limit(1).execute()
        return None
    except Exception as exc:  # noqa: BLE001 - any failure means no Supabase
        return str(exc)[:200]


def _chunks(rows, size=100):
    """Cut a list into small chunks, for bulk inserts."""
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def _select_all(client, table, cols, base=None):
    """Fetch every row from a Supabase table, 1000 at a time.
    PostgREST returns at most 1000 rows in one call, so a single
    call would silently miss the rest — and the seed check would
    then add the missing cars a second time. Small tables finish
    in one call. `base` is an already-filtered query to page
    through instead of a plain table read. Every page is ordered
    by id as well: without a unique order, rows with the same
    price (or no order at all) can appear twice or be skipped
    between pages."""
    rows, start = [], 0
    q = base if base is not None else client.table(table).select(cols)
    q = q.order("id")
    while True:
        page = q.range(start, start + 999).execute().data
        rows.extend(page)
        if len(page) < 1000:
            break
        start += 1000
    return rows


def _seed_cars(client, new_cars):
    """Insert new seed cars. If the Supabase cars table does not
    have the new columns yet (ref, auction_grade, image_url,
    condition_note — added by afridi-trading-bot-add-columns.sql),
    the full insert fails, so try again with only the old columns.
    The cars still get added; the grade and photo are filled in
    later by _backfill_car_details, once the columns exist."""
    if not new_cars:
        return
    try:
        for chunk in _chunks(new_cars):
            client.table("cars").insert(chunk).execute()
    except Exception as exc:  # noqa: BLE001 - columns may not exist yet
        print("Seed with new columns failed, retrying with old "
              f"columns only: {str(exc)[:150]}", flush=True)
        old_fields = ("make", "model", "year", "distance_km",
                      "price_fob", "body_type", "status")
        plain = [{k: car[k] for k in old_fields} for car in new_cars]
        for chunk in _chunks(plain):
            client.table("cars").insert(chunk).execute()


def _backfill_car_details(client):
    """Fill in grade, photo and ref for cars already in Supabase
    that are missing them. Only rows the seed knows about, and
    only fields that are empty — so it does nothing on later
    starts. Skipped quietly if the columns do not exist yet."""
    try:
        have = _select_all(
            client, "cars",
            "id,make,model,year,price_fob,ref,auction_grade,"
            "image_url,condition_note")
    except Exception:  # noqa: BLE001 - new columns may not exist yet
        return
    by_key = {(r["make"], r["model"], r["year"], r["price_fob"]): r
              for r in have}
    fixed = 0
    for row in seed_car_rows():
        key = (row[0], row[1], row[2], row[4])
        old = by_key.get(key)
        if old is None:
            continue
        changes = {}
        for field, value in (("ref", row[7]), ("auction_grade", row[8]),
                             ("image_url", row[9]),
                             ("condition_note", row[10])):
            if value is not None and not old.get(field):
                changes[field] = value
        if changes:
            try:
                client.table("cars").update(changes).eq(
                    "id", old["id"]).execute()
                fixed += 1
            except Exception:  # noqa: BLE001 - keep going car by car
                continue
    if fixed:
        print(f"Backfilled grade/photo for {fixed} cars.", flush=True)


def init_supabase():
    """Seed Supabase if it is empty. The tables already exist
    (made in the Supabase dashboard). Only adds what is missing,
    so running twice is safe."""
    client = _get_sb_client()
    # Cars: add the seed cars that are not there yet. Read ALL rows
    # (see _select_all): one call only returns the first 1000.
    have = {(r["make"], r["model"], r["year"], r["price_fob"])
            for r in _select_all(
                client, "cars", "make,model,year,price_fob")}
    new_cars = []
    for row in seed_car_rows():
        key = (row[0], row[1], row[2], row[4])
        if key not in have:
            new_cars.append({"make": row[0], "model": row[1],
                             "year": row[2], "distance_km": row[3],
                             "price_fob": row[4], "body_type": row[5],
                             "status": row[6], "ref": row[7],
                             "auction_grade": row[8],
                             "image_url": row[9],
                             "condition_note": row[10]})
            have.add(key)
    _seed_cars(client, new_cars)
    # Fill in grade and photo for cars that are already there but
    # were saved before those columns existed. Only touches rows
    # that are missing the data, so later starts do nothing.
    _backfill_car_details(client)
    # Import rules: upsert by country (country is UNIQUE), so the
    # seed values fix any old wrong age limits.
    rules = [{"country": c, "max_car_age_years": a, "notes": n}
             for (c, a, n) in SAMPLE_RULES]
    for chunk in _chunks(rules):
        client.table("import_rules").upsert(
            chunk, on_conflict="country").execute()
    # FAQs: add the seed questions that are not there yet.
    have_q = {r["question"] for r in client.table("faqs").select(
        "question").execute().data}
    new_faqs = [{"question": q, "answer": a, "topic": t}
                for (q, a, t, k) in SAMPLE_FAQS if q not in have_q]
    for chunk in _chunks(new_faqs):
        client.table("faqs").insert(chunk).execute()
    # Sample shipment ATJ-1001, so tracking works at once.
    ships = client.table("shipments").select("id").eq(
        "tracking_no", "ATJ-1001").execute().data
    if not ships:
        user = client.table("users").select("id").eq(
            "email", "buyer@example.com").execute().data
        if user:
            user_id = user[0]["id"]
        else:
            user_id = client.table("users").insert(
                {"name": "Demo Buyer", "email": "buyer@example.com",
                 "country": "Jamaica", "role": "buyer"}).execute().data[0]["id"]
        car = client.table("cars").select("id").order(
            "id").limit(1).execute().data
        if car:
            invoice = client.table("invoices").insert(
                {"user_id": user_id, "car_id": car[0]["id"],
                 "total_price": 2550, "status": "Paid"}).execute().data[0]
            client.table("shipments").insert(
                {"invoice_id": invoice["id"], "vessel": "CNC BANGKOK",
                 "tracking_no": "ATJ-1001", "status": "On the way",
                 "port": "Kingston, Jamaica"}).execute()


def init_db():
    """Make the 10 tables from the proposal, and add sample data."""
    global USE_SUPABASE, _SUPABASE_ERROR
    if USE_SUPABASE:
        # First check Supabase really answers. If it does not
        # (wrong key, or the tables do not let the anon role use
        # them yet), keep running on the local file instead of
        # breaking the whole site. The reason shows on /health.
        _SUPABASE_ERROR = _supabase_probe()
        if _SUPABASE_ERROR is not None:
            print("Supabase test read failed, so the bot keeps using"
                  " the local file for now:", _SUPABASE_ERROR, flush=True)
            USE_SUPABASE = False
        else:
            try:
                init_supabase()
            except Exception as exc:  # noqa: BLE001 - seed is best effort
                print("Supabase seed failed:", exc, flush=True)
            return
    db = sqlite3.connect(DB_FILE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, name TEXT, email TEXT,
            phone TEXT, country TEXT, role TEXT);
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY, user_id INTEGER, level TEXT);
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY, make TEXT, model TEXT, year INTEGER,
            distance_km INTEGER, price_fob INTEGER, body_type TEXT,
            status TEXT, ref TEXT, auction_grade TEXT, image_url TEXT,
            condition_note TEXT);
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY, user_id INTEGER,
            started_at TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY, chat_id INTEGER, sender TEXT,
            text TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY, user_id INTEGER, car_id INTEGER,
            question TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY, user_id INTEGER, car_id INTEGER,
            total_price INTEGER, status TEXT);
        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY, invoice_id INTEGER, vessel TEXT,
            tracking_no TEXT, status TEXT, port TEXT);
        CREATE TABLE IF NOT EXISTS import_rules (
            id INTEGER PRIMARY KEY, country TEXT,
            max_car_age_years INTEGER, notes TEXT);
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY, user_id INTEGER, car_id INTEGER,
            stars INTEGER, comment TEXT);
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY, question TEXT, answer TEXT,
            topic TEXT);
        CREATE TABLE IF NOT EXISTS crawl_queue (
            id INTEGER PRIMARY KEY,
            page_url TEXT,
            page_number INTEGER UNIQUE,
            status TEXT,
            attempts INTEGER DEFAULT 0,
            last_error TEXT,
            created_at TEXT,
            done_at TEXT);
    """)
    # Add a password column to users if the table was made before
    # sign-up existed. Passwords are stored HASHED, never plain text.
    cols = [r[1] for r in db.execute("PRAGMA table_info(users)")]
    if "password_hash" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    # Add a reference column to cars (e.g. AA35371 from the website).
    # The daily sync script uses it to match cars safely.
    car_cols = [r[1] for r in db.execute("PRAGMA table_info(cars)")]
    if "ref" not in car_cols:
        db.execute("ALTER TABLE cars ADD COLUMN ref TEXT")
    # Grade, photo and condition note, from the website listing.
    # Most cars have no grade on the site, so it stays empty.
    for col in ("auction_grade", "image_url", "condition_note"):
        if col not in car_cols:
            db.execute(f"ALTER TABLE cars ADD COLUMN {col} TEXT")
    # Add sample cars only the first time, when the table is empty.
    count = db.execute("SELECT COUNT(*) FROM cars").fetchone()[0]
    if count == 0:
        db.executemany(
            "INSERT INTO cars (make, model, year, distance_km, price_fob,"
            " body_type, status, ref, auction_grade, image_url,"
            " condition_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            seed_car_rows())
    # Add import rules only when that table is empty, so new rules are
    # added even if the cars table already has rows.
    if db.execute("SELECT COUNT(*) FROM import_rules").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO import_rules (country, max_car_age_years, notes)"
            " VALUES (?, ?, ?)", SAMPLE_RULES)
    # Add FAQs only when that table is empty.
    if db.execute("SELECT COUNT(*) FROM faqs").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO faqs (question, answer, topic) VALUES (?, ?, ?)",
            [(q, a, t) for (q, a, t, k) in SAMPLE_FAQS])
        # One sample shipment, so tracking can be tried at once.
        db.execute(
            "INSERT INTO invoices (user_id, car_id, total_price, status)"
            " VALUES (1, 1, 2550, 'Paid')")
        db.execute(
            "INSERT INTO shipments (invoice_id, vessel, tracking_no,"
            " status, port) VALUES (1, 'CNC BANGKOK', 'ATJ-1001',"
            " 'On the way', 'Kingston, Jamaica')")
        db.execute(
            "INSERT INTO users (name, email, country, role)"
            " VALUES ('Demo Buyer', 'buyer@example.com', 'Jamaica',"
            " 'buyer')")
    db.commit()
    db.close()


def _col(row, name):
    """Read one column from a database row, safely. Rows from
    Supabase are dicts; rows from SQLite are sqlite3.Row. Old
    rows may not have the new columns at all, so a missing column
    just gives None instead of an error."""
    try:
        return row[name]
    except (KeyError, IndexError, TypeError):
        return None


def car_condition_text(car):
    """One short sentence about a car's condition, in simple
    words, using only what the website actually says. The grade
    comes from the auction sheet on the site; most cars have no
    grade, so then only the mileage is told. Never invents a
    grade or a condition."""
    parts = []
    grade = _col(car, "auction_grade")
    if grade:
        meaning = GRADES.get(str(grade).lower(), "")
        # GRADES text starts with "Grade 4.5 means ..." — drop that
        # start, so the sentence does not say the grade twice.
        meaning = re.sub(r"^Grade \S+ means ", "", meaning)
        if meaning:
            parts.append(f"Auction grade {grade} — {meaning}")
        else:
            parts.append(f"Auction grade {grade}.")
    note = _col(car, "condition_note")
    if note:
        parts.append(note)
    km = _col(car, "distance_km")
    if km:
        parts.append(f"It has run {km:,} km.")
    return " ".join(parts)


def find_car(text):
    """Find a car in the question by its model name."""
    cars = cached_list("cars", "SELECT * FROM cars")
    for car in cars:
        model = car["model"].lower()
        # "Aqua S" matches "aqua"; "Corolla Axio" matches "axio".
        words = model.replace("corolla ", "").split()
        if any(w in text for w in words if len(w) > 2):
            return car
    return None


def delivered_price(car, country):
    """Work out the delivered price: FOB + shipping + insurance."""
    ship = SHIPPING.get(country, {"port": "your port", "price": 900})
    total = car["price_fob"] + ship["price"] + INSURANCE
    return total, ship["port"]


# ---------- the chatbot brain ----------

# Brand voice: the bot always speaks as Afridi Trading Japan, in
# simple polite words. Its promise is: WHAT YOU SEE IS WHAT YOU RECEIVE.
# Grounded answers: the bot only answers from its own knowledge base
# and database (cars, prices, policies, freight, import rules). It never
# guesses a price, a grade or a refund — if it does not know, it saves
# the question for a human. Guardrails: the bot never promises a price
# or grade it has not checked, never takes money, never changes a price,
# and sends hard questions to a human. Handover: every chat is saved in
# the database with its messages, so the admin can read it and take over.
# ---------- email an unanswered question to the team ----------

# Every unanswered question is emailed to BOTH of these addresses.
INQUIRY_EMAILS = ["csd@afriditrading.com", "sales@afriditrading.com"]


def send_inquiry_email(name, email, question):
    """Email one unanswered question to the Afridi Trading team.

    SMTP settings come ONLY from environment variables (SMTP_HOST,
    SMTP_PORT, SMTP_USER, SMTP_PASS) — never from code. If they are
    not set, the email is skipped and the inquiry stays in the
    database and the admin panel. This never crashes the bot:
    any email problem is only logged.
    """
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if not host or not user or not password:
        print("EMAIL SKIPPED: SMTP settings are not set, so no email "
              "was sent for this inquiry. It is saved in the database.")
        return False
    port = int(os.environ.get("SMTP_PORT", "587"))
    message = EmailMessage()
    message["From"] = user
    message["To"] = ", ".join(INQUIRY_EMAILS)
    message["Subject"] = "New unanswered question - Afridi Trading Bot"
    message.set_content(
        "A customer asked the bot a question it could not answer.\n\n"
        f"Customer: {name}\n"
        f"Email: {email}\n"
        f"Date and time (UTC): {datetime.now().isoformat()}\n\n"
        f"Question:\n{question}\n\n"
        "Please reply to the customer. You can also answer it in the "
        "admin panel, and the bot will learn the answer.")
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(message)
        print("EMAIL SENT: inquiry emailed to "
              f"{', '.join(INQUIRY_EMAILS)}.")
        return True
    except Exception as exc:  # noqa: BLE001 - email must never crash chat
        print(f"EMAIL FAILED: could not send inquiry email: {exc}. "
              "The inquiry is saved in the database.")
        return False


def bot_reply(text, chat_id, user_id=None):
    """Answer one buyer question. Rule-based: keyword matching only."""
    msg = text.lower().strip()
    db = get_db()

    # 0. Real FAQs first: if the question matches a real buyer question
    # from the website, answer with the real answer from the faqs table.
    # Keywords are distinctive phrases, so a price question like
    # "how much is the Aqua to Jamaica" does not match the freight FAQ.
    faqs = cached_list("faqs", "SELECT * FROM faqs")
    for (question, answer, topic, keywords) in SAMPLE_FAQS:
        if any(k in msg for k in keywords):
            row = next((f for f in faqs if f["question"] == question),
                       None)
            if row is not None:
                return row["answer"]
    # Also check every FAQ in the table, including ones the admin added
    # by hand or by answering an unanswered question. Simple word match:
    # if the customer's question shares 2 or more real words with a
    # saved question (or contains it), use that saved answer. Small
    # words like "do", "you", "the" do not count.
    stop = {"do", "you", "the", "a", "an", "is", "are", "can", "i",
            "how", "what", "does", "did", "to", "for", "me", "my",
            "please", "with", "of", "in", "on", "it", "if", "so",
            "your", "our", "we", "us", "and", "or", "am"}
    msg_words = set(re.findall(r"[a-z0-9]+", msg)) - stop
    for f in faqs:
        q_words = set(re.findall(r"[a-z0-9]+",
                                 f["question"].lower())) - stop
        if f["question"].lower() in msg or msg in f["question"].lower():
            return f["answer"]
        overlap = msg_words & q_words
        if len(overlap) >= 2 and len(overlap) * 2 >= len(q_words):
            return f["answer"]

    # 1. Track a shipment: "track ATJ-1001"
    found = re.search(r"atj-?\d+", msg)
    if "track" in msg or found:
        code = ""
        if found:
            digits = re.sub(r"\D", "", found.group(0))
            code = "ATJ-" + digits
        row = db.execute(
            "SELECT * FROM shipments WHERE tracking_no = ?",
            (code,)).fetchone() if code else None
        if row:
            return (f"Shipment {row['tracking_no']} is {row['status']} "
                    f"on {row['vessel']} to {row['port']}.")
        return ("To track your car, send your tracking number, "
                "for example: track ATJ-1001.")

    # 2. Make an invoice: "invoice for the Aqua"
    if "invoice" in msg:
        car = find_car(msg)
        if car:
            total, port = delivered_price(car, "jamaica")
            db.execute(
                "INSERT INTO invoices (user_id, car_id, total_price,"
                " status) VALUES (1, ?, ?, 'Unpaid')",
                (car["id"], total))
            db.commit()
            return (f"Invoice made for the {car['make']} {car['model']} "
                    f"{car['year']}. FOB ${car['price_fob']}. "
                    f"Total with shipping and insurance: ${total}. "
                    "You can see it on the invoice page.")
        return ("Which car do you want an invoice for? "
                "For example: invoice for the Toyota Aqua.")

    # 3a. Condition of one car: "what is the condition of the Aqua"
    # or "what grade is the Aqua". Only what the site says.
    if "condition" in msg or ("grade" in msg and "what is grade" not in msg):
        car = find_car(msg)
        if car:
            detail = car_condition_text(car)
            if detail:
                return (f"The {car['make']} {car['model']} "
                        f"{car['year']}: {detail}")
            return (f"The {car['make']} {car['model']} {car['year']} "
                    "has no auction grade on the website, so I cannot "
                    "tell its grade. Ask our sales team and they will "
                    "check the auction sheet for you.")

    # 3. Explain an auction grade: "what is grade 4"
    if "grade" in msg or "auction sheet" in msg:
        # Match the exact grade named, e.g. "grade 4" or "grade s".
        named = re.search(r"grade\s*([0-9.]+|s|r)\b", msg)
        if named and named.group(1) in GRADES:
            return (GRADES[named.group(1)]
                    + " Ask us if you want the full sheet.")
        return ("Auction grades go from 3 to 5 and S. Grade 5 and S are "
                "the best. Grade 4 is good. Grade 3.5 is fair. "
                "Grade R means the car was repaired. "
                "Ask me about one grade, for example: what is grade 4?")

    # 3b. Policies and freight. These answers use only what the
    # company website (afriditrading.com) actually says. The website
    # does not give an exact freight price or a fixed shipping time,
    # so the bot says that honestly and never invents a number.
    # The freight prices below are the demo sample prices from the
    # SHIPPING list, marked as samples, not live quotes.
    if "refund" in msg or "cancel" in msg:
        return ("Refund and cancellation: the auction security deposit "
                "is 100% refundable. If you cancel a purchase order, "
                "you may need to pay the costs already spent, because "
                "we may have to resell the car. Before you pay, ask "
                "our sales team on WhatsApp and get the terms in "
                "writing on your invoice. See all policies on the "
                "Policies page.")
    if "polic" in msg:
        return ("Our policies, in short: pay only by bank transfer to "
                "our company account in Japan or our WISE business "
                "account, never to a person. Shipping is insured, and "
                "you collect the car at your port with the original "
                "B/L. The auction deposit is 100% refundable, but if "
                "you cancel a purchase order you may pay the costs "
                "already spent. See the full list on the Policies page.")
    if "freight" in msg:
        for country in SHIPPING:
            if country in msg:
                ship = SHIPPING[country]
                return (f"Freight to {ship['port']}: the sample freight "
                        f"in this demo is ${ship['price']}. That is a "
                        "sample, not a live quote. Real freight depends "
                        "on the car size and the port, and the exact "
                        "freight is written on your invoice. Ask for a "
                        "quote for your car and port.")
        return ("Freight depends on the car size and the port, so the "
                "website does not give one fixed freight price. Tell me "
                "your country, for example: how much is freight to "
                "Jamaica? The exact freight is written on your invoice.")
    if "insurance" in msg or "insured" in msg:
        return ("Shipping is insured. The website says: full marine "
                "transit cover. In this demo the delivered price adds "
                f"${INSURANCE} for insurance.")
    if "document" in msg or "b/l" in msg or "bill of lading" in msg \
            or "paper" in msg:
        return ("You get a proforma invoice first. After you pay, we "
                "ship the car and courier the original B/L (bill of "
                "lading) to you, so you can clear the car at your port. "
                "We handle the auction, export papers and shipping.")
    if "collect" in msg or "pick up" in msg or "pickup" in msg:
        return ("You collect the car at your port. We ship it, insured, "
                "and courier the original B/L to you so you can clear "
                "it. Bring the original B/L and your ID to the port.")
    if ("shipping" in msg and ("long" in msg or "time" in msg
                               or "days" in msg or "take" in msg)) \
            or "delivery time" in msg or "how long" in msg:
        return ("Delivery usually takes 4 to 8 weeks. The exact time "
                "depends on the shipping schedule. Once your car is "
                "fully paid, we ship it on the earliest available "
                "vessel. Ask our sales team for the time to your port, "
                "and use your tracking number to follow the ship.")
    if "shipping" in msg or "ship" in msg or "deliver" in msg:
        return ("Shipping policy: we handle the auction, export papers "
                "and shipping. The car is shipped insured, with full "
                "marine transit cover, and you collect it at your port. "
                "Every car shows its delivered price to your port. "
                "Freight depends on the car size and the port.")

    # 4. Find a car by budget: "under $2000" or "budget 3000"
    money = re.search(r"\$?\s?(\d[\d,]*)", msg)
    if "budget" in msg or "under" in msg or "below" in msg or "cheap" in msg:
        amount = int(money.group(1).replace(",", "")) if money else 2000
        rows = db.execute(
            "SELECT * FROM cars WHERE price_fob <= ? ORDER BY price_fob",
            (amount,)).fetchall()
        if rows:
            names = ", ".join(
                f"{c['make']} {c['model']} {c['year']} (${c['price_fob']})"
                for c in rows)
            return f"Cars under ${amount}: {names}."
        return f"No cars under ${amount} in stock right now."

    # 5. Delivered price for one car to one country.
    car = find_car(msg)
    if car and ("how much" in msg or "price" in msg or "cost" in msg
                or "delivered" in msg or "to " in msg):
        detail = car_condition_text(car)
        for country in SHIPPING:
            if country in msg:
                total, port = delivered_price(car, country)
                return (f"The {car['make']} {car['model']} {car['year']} "
                        f"is ${car['price_fob']} in Japan. "
                        f"The delivered price to {port} is ${total} "
                        f"(shipping + ${INSURANCE} insurance). "
                        + (detail + " " if detail else "") +
                        f"Do you want an invoice for this car? Yes / No.")
        return (f"The {car['make']} {car['model']} {car['year']} is "
                f"${car['price_fob']} in Japan. "
                + (detail + " " if detail else "") +
                f"Tell me your country and I will tell you the "
                f"delivered price.")

    # 6. Find a car by make: "show me Toyota cars"
    for make in ("toyota", "honda", "suzuki", "daihatsu"):
        if make in msg:
            rows = db.execute(
                "SELECT * FROM cars WHERE LOWER(make) = ?", (make,)).fetchall()
            names = ", ".join(
                f"{c['model']} {c['year']} (${c['price_fob']})" for c in rows)
            return f"{make.title()} cars in stock: {names}."

    # 7. Import rules for a country. Works for every country in
    # the import_rules table, not just a short list. First try the
    # full country name ("south africa"), then a single word that
    # belongs to only one country ("trinidad", "jamaica"). Words like
    # "south" are shared by several countries, so they need the full
    # name. Age 0 means no age limit; age None means the website does
    # not state an age limit.
    if "import" in msg or "rule" in msg:
        rules = cached_list("rules", "SELECT * FROM import_rules")
        first_words = {}
        for r in rules:
            w = r["country"].lower().split()[0]
            first_words.setdefault(w, []).append(r)
        found = None
        for r in rules:
            if r["country"].lower() in msg:
                found = r
                break
        if found is None:
            for word in re.findall(r"[a-z]+", msg):
                hit = first_words.get(word, [])
                if len(hit) == 1 and word not in ("south", "saint"):
                    found = hit[0]
                    break
        if found:
            age = found["max_car_age_years"]
            if age is None:
                age_text = ("the website does not state an age limit "
                            "for this country — ask our team")
            elif age == 0:
                age_text = "no age limit"
            else:
                age_text = f"up to {age} years old"
            return (f"Import rules for {found['country']}: cars "
                    f"{age_text}. {found['notes']}")

    # 7b. How to buy, auction, prices, stock, inspection.
    # Facts from the website How to Buy, FAQs and import pages.
    if ("how to buy" in msg or "buying step" in msg
            or "how do i buy" in msg or "how can i buy" in msg):
        return ("5 easy buying steps: 1. Search your car. 2. Inquire. "
                "3. Get your invoice. 4. Pay. 5. Shipment. You can buy "
                "from our stock in Japan, UK, Thailand and Korea, or "
                "buy a pre-shipped car. You can also discuss the price "
                "with our team before you pay.")
    if "auction" in msg or "bid" in msg:
        return ("You can buy cars from Japan's auctions through us. "
                "Register, talk to a sales representative, and pay a "
                "security deposit (100% refundable) to start bidding. "
                "You bid up to your account credit limit. We are "
                "members of all auction houses in Japan, with about "
                "100,000 cars each week. After you win, we ask for the "
                "deposit to ship, and once fully paid we send the final "
                "documents so you can release the car at your port.")
    if "fob" in msg or "cif" in msg or "c&f" in msg or "c and f" in msg:
        return ("FOB means the price in Japan. Extra costs are freight, "
                "clearance, import duty, registration and compliance "
                "fees. C&F means the FOB price plus freight. CIF means "
                "FOB plus freight plus insurance. Tell me your country "
                "and I will work out your delivered price.")
    if "inspect" in msg:
        return ("Yes, all cars go through a full inspection to make "
                "sure they match the details on the auction sheet. Our "
                "skilled team also inspects cars before we bid on them.")
    if "how many cars" in msg or "stock" in msg:
        return ("We have over 2,000 cars in our regular stock, and "
                "about 100,000 cars each week through the Japan "
                "auctions. Tell me a make or a budget and I will show "
                "you cars.")
    if "lhd" in msg or "left hand" in msg:
        return ("Left-hand drive cars are rare in Japan, but we can find "
                "them in our Korean and American stock. Ask us for the "
                "model you want.")
    if "ro-ro" in msg or "roro" in msg or "container" in msg:
        return ("We ship by RO-RO and by container, to Europe, Asia, "
                "Africa, the Black Sea, the Caribbean, North and South "
                "America, Oceania, the Middle East and East Asia. Ask "
                "for your port and we will tell you the way we ship.")
    if "negotiat" in msg or "discount" in msg:
        return ("Yes, you can discuss the price with our expert team "
                "before you pay. Send your offer and we will reply.")

    # 8. Payment policy.
    if "pay" in msg or "payment" in msg or "bank" in msg:
        return ("Payment policy: pay by telegraphic transfer to our "
                "company bank account in Japan, or by Visa, Mastercard "
                "or PayPal. We also take WISE business account payments. "
                "The beneficiary is always Afridi Trading. Never pay to "
                "a person, never use Western Union, and never pay a "
                "local agent — our agents cannot take payments. Bank "
                "fees are paid by the buyer. Before you pay, verify the "
                "person at afriditrading.com/verify. Ask us for the "
                "official proforma invoice first, and pay only the "
                "amount on that invoice.")

    # 9. Hello, hours, contact.
    if any(w in msg for w in ("hello", "hi", "salam", "hey")):
        return ("Hello! I am the Afridi Trading Bot from Afridi "
                "Trading Japan — what you see is what you receive. Ask "
                "me about a car, a price, an auction grade, shipping, "
                "or import rules.")
    if ("hour" in msg or "open" in msg or "contact" in msg
            or "whatsapp" in msg or "tiktok" in msg or "facebook" in msg):
        return ("Contact us: WhatsApp sales +81 80 5173 0786 or "
                "+81 70 4457 0584, customer support +81 80 7256 3364. "
                "Website: afriditrading.com. Facebook: "
                "facebook.com/afriditradingjapan. TikTok: "
                "@afriditradingjapan. Office hours are Monday to Friday "
                "9 to 6, Saturday 9 to 4, Japan time. I am here day and "
                "night.")

    # 10. I do not know: save the question for a human, as an
    # open inquiry with the customer who asked it (None = guest).
    db.execute(
        "INSERT INTO inquiries (user_id, car_id, question, status)"
        " VALUES (?, NULL, ?, 'open')", (user_id, text))
    db.commit()
    # Also email it to the team at once, so they can reply. If email
    # is not set up, this only logs a message and the inquiry still
    # waits in the admin panel.
    name, email = "Guest", "not given"
    if user_id is not None:
        who = db.execute("SELECT name, email FROM users WHERE id = ?",
                         (user_id,)).fetchone()
        if who is not None:
            name, email = who["name"], who["email"]
    send_inquiry_email(name, email, text)
    return ("I do not know that yet. I saved your question for our team, "
            "and a human will reply. You can also ask me about a car, "
            "a price, a grade, shipping, or import rules.")


# ---------- web pages ----------

@app.route("/")
def home():
    """Home page with the chat window."""
    return render_template("index.html")


# ---------- sign-up, sign-in, my chats ----------

@app.route("/auth/sign-up", methods=["GET", "POST"])
def sign_up():
    """Sign-up page: name, email and password only. No Google login."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or "@" not in email or len(password) < 4:
            return render_template("signup.html", error="Please fill in "
                                   "your name, a real email, and a "
                                   "password of 4 letters or more.")
        db = get_db()
        exists = db.execute("SELECT id FROM users WHERE email = ?",
                            (email,)).fetchone()
        if exists:
            return render_template(
                "signup.html",
                error="That email already has an account. Please sign in.")
        role = role_for_email(email)
        db.execute(
            "INSERT INTO users (name, email, country, role, password_hash)"
            " VALUES (?, ?, '', ?, ?)",
            (name, email, role, generate_password_hash(password)))
        db.commit()
        user = db.execute("SELECT * FROM users WHERE email = ?",
                          (email,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("home"))
    return render_template("signup.html", error=None)


@app.route("/auth/sign-in", methods=["GET", "POST"])
def sign_in():
    """Sign-in page: email and password."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?",
                          (email,)).fetchone()
        if user is None or not user["password_hash"] or not \
                check_password_hash(user["password_hash"], password):
            return render_template(
                "signin.html",
                error="Wrong email or password. Please try again.")
        # The admin email is SUPER_ADMIN even if the account is old.
        if user["role"] != role_for_email(email):
            db.execute("UPDATE users SET role = ? WHERE id = ?",
                       (role_for_email(email), user["id"]))
            db.commit()
            user = db.execute("SELECT * FROM users WHERE id = ?",
                              (user["id"],)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("home"))
    return render_template("signin.html", error=None)


@app.route("/auth/sign-out")
def sign_out():
    """Sign out and go back to the home page."""
    session.clear()
    return redirect(url_for("home"))


@app.route("/my-chats")
def my_chats():
    """My chats: all the signed-in user's old chats, newest first."""
    user = current_user()
    if user is None:
        return redirect(url_for("sign_in"))
    db = get_db()
    chats = db.execute(
        "SELECT c.*, COUNT(m.id) AS messages FROM chats c"
        " LEFT JOIN messages m ON m.chat_id = c.id"
        " WHERE c.user_id = ? GROUP BY c.id ORDER BY c.id DESC",
        (user["id"],)).fetchall()
    return render_template("my_chats.html", chats=chats)


@app.route("/my-chats/<int:chat_id>")
def view_chat(chat_id):
    """One old chat, with all its messages."""
    user = current_user()
    if user is None:
        return redirect(url_for("sign_in"))
    db = get_db()
    chat = db.execute(
        "SELECT * FROM chats WHERE id = ? AND user_id = ?",
        (chat_id, user["id"])).fetchone()
    if chat is None:
        return "Chat not found.", 404
    messages = db.execute(
        "SELECT * FROM messages WHERE chat_id = ? ORDER BY id",
        (chat_id,)).fetchall()
    return render_template("chat_view.html", chat=chat, messages=messages)


# ---------- admin panel (admin only) ----------

@app.route("/admin")
def admin():
    """Admin dashboard: health, usage, lists and FAQs. Admin only."""
    user = current_user()
    if not is_admin(user):
        return redirect(url_for("sign_in"))
    db = get_db()
    try:
        db.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    tables = db.execute(
        "SELECT COUNT(*) FROM sqlite_master"
        " WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
    counts = {
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "chats": db.execute("SELECT COUNT(*) FROM chats").fetchone()[0],
        "messages": db.execute(
            "SELECT COUNT(*) FROM messages").fetchone()[0],
        "invoices": db.execute(
            "SELECT COUNT(*) FROM invoices").fetchone()[0],
        "inquiries": db.execute(
            "SELECT COUNT(*) FROM inquiries").fetchone()[0],
        "faqs": db.execute("SELECT COUNT(*) FROM faqs").fetchone()[0],
        "messages_today": db.execute(
            "SELECT COUNT(*) FROM messages"
            " WHERE substr(created_at, 1, 10) = date('now')").fetchone()[0],
    }
    users = db.execute(
        "SELECT * FROM users ORDER BY id DESC LIMIT 10").fetchall()
    chats = db.execute(
        "SELECT c.*, u.name AS user_name FROM chats c"
        " LEFT JOIN users u ON u.id = c.user_id"
        " ORDER BY c.id DESC LIMIT 10").fetchall()
    messages = db.execute(
        "SELECT * FROM messages ORDER BY id DESC LIMIT 50").fetchall()
    questions = db.execute(
        "SELECT i.*, u.name AS user_name, u.email AS user_email"
        " FROM inquiries i LEFT JOIN users u ON u.id = i.user_id"
        " WHERE i.status = 'open' ORDER BY i.id DESC").fetchall()
    faqs = db.execute("SELECT * FROM faqs ORDER BY id").fetchall()
    cars = db.execute("SELECT * FROM cars").fetchall()
    invoices = db.execute("SELECT * FROM invoices").fetchall()
    ships = db.execute("SELECT * FROM shipments").fetchall()
    # Crawl queue: how many stock pages are done, waiting, failed.
    # The queue worker (scripts/crawl_queue.py) fills this table.
    # On Vercel the database starts fresh, so the queue is empty
    # there — the real queue lives where the worker runs.
    queue_rows = db.execute(
        "SELECT status, COUNT(*) AS n FROM crawl_queue"
        " GROUP BY status").fetchall()
    queue_counts = {r["status"]: r["n"] for r in queue_rows}
    queue_last = db.execute(
        "SELECT * FROM crawl_queue ORDER BY page_number DESC"
        " LIMIT 20").fetchall()
    return render_template(
        "admin.html", health={"app": "Running", "db_ok": db_ok,
                              "tables": tables,
                              "db_mode": "supabase" if USE_SUPABASE
                              else "sqlite",
                              "supabase_error": _SUPABASE_ERROR,
                              "cache_hits": _CACHE_STATS["hits"],
                              "cache_misses": _CACHE_STATS["misses"],
                              "cached_tables": sorted(_CACHE.keys())},
        counts=counts, users=users, chats=chats, messages=messages,
        questions=questions, faqs=faqs, cars=cars, invoices=invoices,
        ships=ships, queue_counts=queue_counts, queue_last=queue_last)


@app.route("/admin/inquiry/answer/<int:inquiry_id>", methods=["POST"])
def admin_inquiry_answer(inquiry_id):
    """Admin answers an unanswered question. Two things happen:
    (1) the inquiry is marked 'answered', (2) the question + answer
    are added to the faqs table as a new chunk of knowledge, so the
    next customer who asks the same question gets the answer at once.
    The FAQ cache is cleared so the new answer works immediately."""
    user = current_user()
    if not is_admin(user):
        return redirect(url_for("sign_in"))
    answer = request.form.get("answer", "").strip()
    topic = request.form.get("topic", "").strip() or "general"
    if answer:
        db = get_db()
        inquiry = db.execute(
            "SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
        if inquiry is not None:
            db.execute("INSERT INTO faqs (question, answer, topic)"
                       " VALUES (?, ?, ?)",
                       (inquiry["question"], answer, topic))
            db.execute("UPDATE inquiries SET status = 'answered'"
                       " WHERE id = ?", (inquiry_id,))
            db.commit()
            _CACHE.pop("faqs", None)
    return redirect(url_for("admin"))


@app.route("/admin/faq/add", methods=["POST"])
def admin_faq_add():
    """Admin adds one FAQ. Clears the FAQ cache so it shows at once."""
    user = current_user()
    if not is_admin(user):
        return redirect(url_for("sign_in"))
    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()
    topic = request.form.get("topic", "").strip() or "general"
    if question and answer:
        db = get_db()
        db.execute("INSERT INTO faqs (question, answer, topic)"
                   " VALUES (?, ?, ?)", (question, answer, topic))
        db.commit()
        _CACHE.pop("faqs", None)
    return redirect(url_for("admin"))


@app.route("/admin/faq/delete/<int:faq_id>", methods=["POST"])
def admin_faq_delete(faq_id):
    """Admin deletes one FAQ. Clears the FAQ cache too."""
    user = current_user()
    if not is_admin(user):
        return redirect(url_for("sign_in"))
    db = get_db()
    db.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
    db.commit()
    _CACHE.pop("faqs", None)
    return redirect(url_for("admin"))


@app.route("/health")
def health():
    """Tiny health page: is the bot up, and is the cache working?
    Also shows which database is live (supabase or sqlite)."""
    info = {
        "status": "ok",
        "db": "supabase" if USE_SUPABASE else "sqlite",
        "cache_hits": _CACHE_STATS["hits"],
        "cache_misses": _CACHE_STATS["misses"],
        "cached_tables": sorted(_CACHE.keys()),
    }
    if _SUPABASE_ERROR:
        info["supabase_error"] = _SUPABASE_ERROR
    return jsonify(info)


@app.route("/policies")
def policies():
    """Policies page: payment, shipping, freight, insurance, documents."""
    return render_template("policies.html")


@app.route("/cars")
def cars():
    """Car list page, with search by budget and make.

    The page also gets the list of makes (with counts) and the
    make-logo links, so the search bar, make filter, rows filter
    and logos all work in the browser without a page reload.
    """
    db = get_db()
    budget = request.args.get("budget", type=int)
    make = request.args.get("make", "")
    rows = db.execute("SELECT * FROM cars ORDER BY price_fob").fetchall()
    if budget:
        rows = [c for c in rows if c["price_fob"] <= budget]
    if make:
        rows = [c for c in rows if c["make"].lower() == make.lower()]
    # Only cars WITH a photo are shown on this page. Cars without
    # a photo stay in the database (they may get a photo later) —
    # they are just hidden here, from the list, the search and the
    # make counts. So "X cars found" only ever counts photo cars.
    def _val(car, name):
        try:
            return car[name]
        except (KeyError, IndexError, TypeError):
            return None
    rows = [c for c in rows if _val(c, "image_url")]
    make_counts = {}
    for c in rows:
        make_counts[c["make"]] = make_counts.get(c["make"], 0) + 1
    makes = sorted(make_counts, key=lambda m: (-make_counts[m], m))
    return render_template("cars.html", cars=rows,
                           budget=budget, make=make,
                           makes=makes, make_counts=make_counts,
                           make_logos=MAKE_LOGOS)


def make_qr_data_uri(text):
    """Make a QR code picture for one short text (an invoice URL)
    and return it as a data URI, so the invoice page can show it
    with no file to upload and no outside website involved.
    Returns None if the qrcode package is not installed."""
    if qrcode is None:
        return None
    import base64
    import io
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=8, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return ("data:image/png;base64,"
            + base64.b64encode(buf.getvalue()).decode("ascii"))


@app.route("/invoice/<int:car_id>")
def invoice(car_id):
    """Proforma invoice page for one car, in the same format as
    the real Afridi Trading invoice. No customer or consignee
    details are shown anywhere on this page — only the company
    (BILL FROM), the vehicle and the bank details. The bot has no
    chassis number and no deposit ratio, so those cells show "—"
    instead of a made-up value. The QR code under SCAN TO VERIFY
    is made automatically for this invoice only: scanning it
    opens this exact invoice page, so anyone can check it is real.
    The QR holds only the invoice web address — no personal
    details of any kind."""
    db = get_db()
    car = db.execute("SELECT * FROM cars WHERE id = ?",
                     (car_id,)).fetchone()
    if car is None:
        return "Car not found.", 404
    total, port = delivered_price(car, "jamaica")
    fob = _col(car, "price_fob") or 0
    today = datetime.now(timezone.utc).date()
    valid = today + timedelta(days=14)
    invoice_url = "%s/invoice/%d" % (LIVE_SITE, car_id)
    return render_template(
        "invoice.html", car=car, total=total, port=port,
        ship_cost=total - fob,
        invoice_no="ATJ-%04d" % car_id,
        issue_date=today.isoformat(),
        valid_date=valid.isoformat(),
        due_date=valid.isoformat(),
        invoice_url=invoice_url,
        qr_data_uri=make_qr_data_uri(invoice_url))


@app.route("/track")
def track():
    """Tracking page. Give ?code=ATJ-1001 to see one shipment."""
    db = get_db()
    code = request.args.get("code", "")
    ship = None
    if code:
        ship = db.execute(
            "SELECT * FROM shipments WHERE tracking_no = ?",
            (code.upper(),)).fetchone()
    return render_template("track.html", code=code, ship=ship)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Chat API. JavaScript sends a message, the bot answers as JSON.
    If the question is about one car that has a photo, the photo
    link is sent too, so the chat can show the car."""
    data = request.get_json(force=True)
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"reply": "Please type a question first."})
    # Guests can still chat, but guest chats are NOT saved.
    # Only signed-in users get their chat history saved.
    user = current_user()
    if user is None:
        reply = bot_reply(text, None, None)
        answer = {"reply": reply}
        photo = _car_photo(text)
        if photo:
            answer["photo"] = photo
        return jsonify(answer)
    db = get_db()
    chat = db.execute(
        "SELECT id FROM chats WHERE user_id = ? AND status = 'Open'"
        " ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
    if chat is None:
        db.execute("INSERT INTO chats (user_id, started_at, status)"
                   " VALUES (?, ?, 'Open')",
                   (user["id"], datetime.now().isoformat()))
        db.commit()
        chat = db.execute(
            "SELECT id FROM chats WHERE user_id = ?"
            " ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
    now = datetime.now().isoformat()
    db.execute("INSERT INTO messages (chat_id, sender, text, created_at)"
               " VALUES (?, 'buyer', ?, ?)", (chat["id"], text, now))
    reply = bot_reply(text, chat["id"], user["id"])
    db.execute("INSERT INTO messages (chat_id, sender, text, created_at)"
               " VALUES (?, 'bot', ?, ?)", (chat["id"], reply, now))
    db.commit()
    answer = {"reply": reply, "chat_id": chat["id"]}
    photo = _car_photo(text)
    if photo:
        answer["photo"] = photo
    return jsonify(answer)


def _car_photo(text):
    """Photo link of the one car the question asks about, or None.
    Only used for the chat reply — the photo itself is shown by
    the chat window, never as a broken image."""
    car = find_car(text.lower())
    if car is None:
        return None
    return _col(car, "image_url")


@app.route("/api/cars")
def api_cars():
    """Simple JSON list of cars, for the search page."""
    db = get_db()
    rows = db.execute("SELECT * FROM cars ORDER BY price_fob").fetchall()
    return jsonify([dict(r) for r in rows])


# Make the database when the app starts. On Vercel this runs once
# on a cold start; running "python app.py" also calls it below.
# It is safe to run twice: tables are only made if missing, and
# sample cars are only added when the cars table is empty.
init_db()


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
