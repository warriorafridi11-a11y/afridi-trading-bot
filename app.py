"""
Afridi Trading Bot — a simple chatbot for buying Japanese used cars.
Written in easy Python + Flask, in one file, so a student can explain it.
The bot is rule-based: it looks for keywords in the buyer's question
and answers from its knowledge base. No deep learning, no paid API.
"""

import os
import re
import sqlite3
from datetime import datetime

from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)

# The database is one small file. It is made by itself the first time.
# On Vercel the code folder is read-only, so the file goes in /tmp.
if os.environ.get("VERCEL"):
    DB_FILE = "/tmp/bot.db"
else:
    DB_FILE = os.path.join(os.path.dirname(__file__), "bot.db")

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

# Sample cars, like the cars on afriditrading.com. Price is the FOB price.
SAMPLE_CARS = [
    ("Toyota", "Aqua S", 2016, 140000, 1600, "Hybrid", "In stock"),
    ("Toyota", "Aqua S", 2014, 172000, 1500, "Hybrid", "In stock"),
    ("Toyota", "Vitz F", 2011, 255000, 2750, "Hatchback", "In stock"),
    ("Toyota", "Vitz F", 2014, 32000, 4000, "Hatchback", "In stock"),
    ("Toyota", "Voxy Hybrid X", 2017, 212000, 6500, "Minivan", "In stock"),
    ("Toyota", "Corolla Axio", 2017, 128000, 3300, "Sedan", "In stock"),
    ("Honda", "Vezel", 2018, 98000, 4550, "SUV", "In stock"),
    ("Honda", "Fit", 2016, 115000, 1150, "Hatchback", "In stock"),
    ("Suzuki", "Swift XG", 2014, 99000, 2000, "Hatchback", "In stock"),
    ("Toyota", "Sienta Hybrid G", 2016, 277000, 3100, "Minivan", "In stock"),
]

# Sample import rules. These are simple demo rules, not legal advice.
# Import age limits from the website import page (afriditrading.com/import).
# 0 means no age limit on that page. These are simple demo rules,
# not legal advice — the full guide is on the website.
SAMPLE_RULES = [
    ("Jamaica", 5, "Ask us for the full guide."),
    ("Trinidad and Tobago", 5, "Ask us for the full guide."),
    ("Ghana", 10, "Ask us for the full guide."),
    ("Kenya", 8, "Ask us for the full guide."),
    ("Antigua and Barbuda", 0, "Ask us for the full guide."),
    ("Nigeria", 15, "Ask us for the full guide."),
    ("Uganda", 15, "Ask us for the full guide."),
    ("Namibia", 12, "Ask us for the full guide."),
    ("Pakistan", 3, "Ask us for the full guide."),
    ("Bangladesh", 4, "Ask us for the full guide."),
    ("India", 3, "Ask us for the full guide."),
    ("Mauritius", 4, "Ask us for the full guide."),
    ("Egypt", 1, "Ask us for the full guide."),
    ("Angola", 5, "Ask us for the full guide."),
    ("South Africa", 0, "No age restriction. Ask us for the full guide."),
    ("Tanzania", 0, "Ask us for the full guide."),
    ("Zambia", 0, "Ask us for the full guide."),
]


# ---------- database helpers ----------

def get_db():
    """Open one database link for this web request."""
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


def init_db():
    """Make the 10 tables from the proposal, and add sample data."""
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
            status TEXT);
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
    """)
    # Add sample cars only the first time, when the table is empty.
    count = db.execute("SELECT COUNT(*) FROM cars").fetchone()[0]
    if count == 0:
        db.executemany(
            "INSERT INTO cars (make, model, year, distance_km, price_fob,"
            " body_type, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            SAMPLE_CARS)
    # Add import rules only when that table is empty, so new rules are
    # added even if the cars table already has rows.
    if db.execute("SELECT COUNT(*) FROM import_rules").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO import_rules (country, max_car_age_years, notes)"
            " VALUES (?, ?, ?)", SAMPLE_RULES)
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


def find_car(text):
    """Find a car in the question by its model name."""
    db = get_db()
    cars = db.execute("SELECT * FROM cars").fetchall()
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
def bot_reply(text, chat_id):
    """Answer one buyer question. Rule-based: keyword matching only."""
    msg = text.lower().strip()
    db = get_db()

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
        for country in SHIPPING:
            if country in msg:
                total, port = delivered_price(car, country)
                return (f"The {car['make']} {car['model']} {car['year']} "
                        f"is ${car['price_fob']} in Japan. "
                        f"The delivered price to {port} is ${total} "
                        f"(shipping + ${INSURANCE} insurance). "
                        f"Do you want an invoice for this car? Yes / No.")
        return (f"The {car['make']} {car['model']} {car['year']} is "
                f"${car['price_fob']} in Japan. "
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

    # 7. Import rules for a country.
    for country in ("jamaica", "trinidad", "ghana", "kenya", "antigua",
                    "nigeria", "uganda", "namibia", "pakistan", "bangladesh",
                    "india", "mauritius", "egypt", "angola", "south africa",
                    "tanzania", "zambia"):
        if country in msg:
            row = db.execute(
                "SELECT * FROM import_rules WHERE LOWER(country) LIKE ?",
                ("%" + country + "%",)).fetchone()
            if row:
                age = (f"up to {row['max_car_age_years']} years old"
                       if row["max_car_age_years"] else "no age limit")
                return (f"Import rules for {row['country']}: cars {age}. "
                        f"{row['notes']}")

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
        return ("We have over 1,000 cars in our regular stock, and "
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

    # 10. I do not know: save the question for a human.
    db.execute(
        "INSERT INTO inquiries (user_id, car_id, question, status)"
        " VALUES (1, NULL, ?, 'Open')", (text,))
    db.commit()
    return ("I do not know that yet. I saved your question for our team, "
            "and a human will reply. You can also ask me about a car, "
            "a price, a grade, shipping, or import rules.")


# ---------- web pages ----------

@app.route("/")
def home():
    """Home page with the chat window."""
    return render_template("index.html")


@app.route("/policies")
def policies():
    """Policies page: payment, shipping, freight, insurance, documents."""
    return render_template("policies.html")


@app.route("/cars")
def cars():
    """Car list page, with search by budget and make."""
    db = get_db()
    budget = request.args.get("budget", type=int)
    make = request.args.get("make", "")
    rows = db.execute("SELECT * FROM cars ORDER BY price_fob").fetchall()
    if budget:
        rows = [c for c in rows if c["price_fob"] <= budget]
    if make:
        rows = [c for c in rows if c["make"].lower() == make.lower()]
    return render_template("cars.html", cars=rows,
                           budget=budget, make=make)


@app.route("/invoice/<int:car_id>")
def invoice(car_id):
    """Invoice page for one car."""
    db = get_db()
    car = db.execute("SELECT * FROM cars WHERE id = ?",
                     (car_id,)).fetchone()
    if car is None:
        return "Car not found.", 404
    total, port = delivered_price(car, "jamaica")
    return render_template("invoice.html", car=car, total=total, port=port)


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


@app.route("/admin")
def admin():
    """Admin page: all chats, cars, invoices and shipments."""
    db = get_db()
    chats = db.execute(
        "SELECT * FROM messages ORDER BY id DESC LIMIT 50").fetchall()
    cars = db.execute("SELECT * FROM cars").fetchall()
    invoices = db.execute("SELECT * FROM invoices").fetchall()
    ships = db.execute("SELECT * FROM shipments").fetchall()
    questions = db.execute(
        "SELECT * FROM inquiries WHERE status = 'Open'").fetchall()
    return render_template("admin.html", chats=chats, cars=cars,
                           invoices=invoices, ships=ships,
                           questions=questions)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Chat API. JavaScript sends a message, the bot answers as JSON."""
    data = request.get_json(force=True)
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"reply": "Please type a question first."})
    db = get_db()
    chat = db.execute(
        "SELECT id FROM chats ORDER BY id DESC LIMIT 1").fetchone()
    if chat is None:
        db.execute("INSERT INTO chats (user_id, started_at, status)"
                   " VALUES (1, ?, 'Open')",
                   (datetime.now().isoformat(),))
        db.commit()
        chat = db.execute(
            "SELECT id FROM chats ORDER BY id DESC LIMIT 1").fetchone()
    now = datetime.now().isoformat()
    db.execute("INSERT INTO messages (chat_id, sender, text, created_at)"
               " VALUES (?, 'buyer', ?, ?)", (chat["id"], text, now))
    reply = bot_reply(text, chat["id"])
    db.execute("INSERT INTO messages (chat_id, sender, text, created_at)"
               " VALUES (?, 'bot', ?, ?)", (chat["id"], reply, now))
    db.commit()
    return jsonify({"reply": reply})


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
