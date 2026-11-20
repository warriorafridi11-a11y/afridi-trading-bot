# Afridi Trading Bot

An AI chatbot for buying Japanese used cars from Afridi Trading Japan.
A final-year project for IQRA National University, Peshawar.

The bot talks to buyers day and night. It answers questions, helps find a
car by budget and make, explains auction grades in simple words, works out
the delivered price to a port, makes an invoice, explains safe payment,
tracks a shipment, and answers import rules for each country.

The bot is **rule-based**: it looks for keywords in the question and answers
from its knowledge base. No deep learning, no paid API, no OpenAI key needed.

## How to run it

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

The database file `bot.db` is made by itself the first time you run the app.
It has 10 tables: users, admins, cars, chats, messages, inquiries, invoices,
shipments, import_rules, reviews. Sample cars and import rules are added
automatically.

## Try the bot

- "How much is the Toyota Aqua to Jamaica?"
- "Show me cars under $2000"
- "What is grade 4?"
- "Invoice for the Toyota Vitz"
- "Track ATJ-1001"
- "Import rules for Ghana"

## Policies and freight

The bot also answers policy and freight questions, using only what
afriditrading.com actually says. It explains the payment policy (bank
transfer only to the company account in Japan or the WISE business
account, never to a person), the shipping policy, freight (freight
depends on the car size and the port, so the bot gives the demo sample
freight and says the exact freight is on the invoice), delivery time
(the website gives no fixed time), marine insurance (full marine
transit cover), the documents you get (invoice and original B/L), and
collecting the car at the port. The website does not publish a refund
policy, so the bot says that honestly and tells the buyer to ask sales
before paying. Read them all on the `/policies` page.

## How the bot is built (simple production-agent ideas)

1. **Brand voice:** the bot always speaks as Afridi Trading Japan, in
   simple polite words — "WHAT YOU SEE IS WHAT YOU RECEIVE".
2. **True answers only:** the bot only answers from its own knowledge base
   and database (cars, prices, policies, freight, import rules). If it
   does not know, it says so and saves the question for a human instead
   of guessing a price, grade or refund.
3. **Tool actions:** the bot can do things, not just talk — make an
   invoice, track a shipment, save an inquiry for a human.
4. **Guardrails:** it never promises a price or grade it has not checked,
   never takes money, never changes a price, and sends hard questions to
   a human.
5. **Human handover:** every chat is saved in the database with its
   messages, so the admin can read it and take over.

No paid API, no vector database, no real RAG library — just the simple
version a student can explain.

## Real FAQs and a simple cache

The bot keeps a `faqs` table with 20 real buyer questions and answers
taken from afriditrading.com (buying steps, payment, refund, shipping,
freight, delivery time, insurance, documents, port, FOB, grades,
auction, stock, hidden charges, left-hand drive, scam checks, contact,
shipping countries, tracking). It checks the FAQs first, by keyword,
before its other rules — so real questions get real answers.

It also has a simple in-memory cache: a plain Python dict with a
5-minute time limit for the car list, the FAQs and the import rules.
Repeated questions do not go to the database every time. After
5 minutes the cache refreshes, so new data shows up soon. No Redis,
no extra service. See the cache hits and misses on `/health`.

## Car photos and auction grades

Every car card on `/cars` shows the car's real photo from
afriditrading.com, with the auction grade next to the year and
mileage when the site lists one (for example "Grade 4.5"). Most
cars on the site have no grade at all — the bot never invents
one, and says so honestly when a buyer asks. When the bot
answers about one car in chat, it tells the grade in simple
words ("Grade 4.5 — very good shape, a few small marks only")
and the mileage, and the chat shows the car's photo under the
answer. Cars with no photo show a plain grey box, never a
broken image. The photo link, grade and condition note live in
the cars table (`image_url`, `auction_grade`, `condition_note`).

## Pages

- `/` — home page with the chat window
- `/cars` — car list, search by budget and make
- `/policies` — policies: payment, shipping, freight, insurance, documents, refunds
- `/invoice/<car id>` — invoice for one car
- `/track` — track a shipment, try `ATJ-1001`
- `/auth/sign-up` and `/auth/sign-in` — customer accounts (see below)
- `/my-chats` — a signed-in customer's saved chats
- `/admin` — admin panel (admin only): health, usage, users, chats,
  open questions, FAQs (add/delete), cars, invoices, shipments

## Sign-up and admin

Customers can sign up with name, email and password. The password is
stored HASHED (werkzeug `generate_password_hash`), never plain text.
When a customer is signed in, their chats and messages are saved under
their user id, and they can open old chats again from "My chats", so
they never lose chat history. Guests can still chat, but guest chats
are not saved — the home page says so honestly.

`warriorafridi11@gmail.com` is the admin (`ADMIN_EMAIL` in app.py).
When that email signs up or signs in, the account becomes SUPER_ADMIN.
The admin page shows health (app running, database ok, cache hits and
misses, number of tables), usage (users, chats, messages, messages
today, invoices, open questions, FAQs), recent users and chats, and
lets the admin add or delete FAQs.

## Email for unanswered questions

When the bot cannot answer a question, it saves the question as an
open inquiry AND emails it at once to BOTH
**csd@afriditrading.com** and **sales@afriditrading.com**, with the
customer's name and email (if given), the question, and the date/time.
If the email settings below are not set, the inquiry is still saved
in the database and shown in the admin panel, and the code only logs
"EMAIL SKIPPED" — the chat never crashes.

To turn the email on, Wahaab must add these 4 environment variables
in Vercel (Dashboard > project **afridi-trading-bot** > Settings >
Environment Variables, then redeploy so they take effect):

- `SMTP_HOST` = `smtp.gmail.com`
- `SMTP_PORT` = `587`
- `SMTP_USER` = the Gmail address that sends the email
- `SMTP_PASS` = a Gmail **App Password** (16 letters), NOT the normal
  Gmail password. Make one here: Google Account > Security > turn on
  2-Step Verification > App passwords > pick "Mail" > copy the
  16-letter password it shows. Never put the password in code,
  GitHub, or chat.

## Daily sync for new and sold vehicles

Script: `scripts/sync_vehicles.py` (plain Python, no extra package).
It reads the stock pages on afriditrading.com with plain HTTP, adds
new cars to the Supabase cars table, updates the price if a car
changed, and marks cars that are gone from the website as `sold`
(it never deletes a row). It only marks cars sold on a FULL crawl.
The bot's cache refreshes within 5 minutes, so the new data shows
up in the bot soon after the sync runs.

The script reads the full car data the listing page hides as JSON:
the photo link, the auction grade, the website reference, the
trim, the mileage and the fuel. It waits 3 seconds between pages
and stops at once on error 429 (too many requests).

Exact commands (run from the repo folder):

- Look only, change nothing:
  `python3 scripts/sync_vehicles.py --dry-run --max-pages 2`
- Normal daily run (first 10 pages):
  `SUPABASE_URL=https://jlbapnqzntqlyjuqvtmq.supabase.co SUPABASE_ANON_KEY=<anon key> python3 scripts/sync_vehicles.py`
- Crawl more pages, starting at a later page, and save the cars
  to a file as well:
  `SUPABASE_URL=https://jlbapnqzntqlyjuqvtmq.supabase.co SUPABASE_ANON_KEY=<anon key> python3 scripts/sync_vehicles.py --start-page 38 --max-pages 47 --out /tmp/new_cars.json`
- Full sync (all pages — this is the one that marks sold cars):
  `SUPABASE_URL=https://jlbapnqzntqlyjuqvtmq.supabase.co SUPABASE_ANON_KEY=<anon key> python3 scripts/sync_vehicles.py --max-pages 0`

The script prints a summary at the end: `new=X updated=Y marked
sold=Z`, plus the sync time. No schedule is set up in this repo —
the daily schedule will be set up separately. The Supabase cars
table needs a `ref` column first (the seed SQL file adds it), plus
the `auction_grade`, `image_url` and `condition_note` columns
(see `afridi-trading-bot-add-columns.sql` in your_files).

## Crawl queue — getting ALL the cars, slowly

The website has about 38,000 cars on about 1,600 stock pages. Asking
for them all at once gets us blocked (error 429). So the queue works
like a line at a shop: one page at a time, 3 seconds wait between
pages, and it remembers which pages are done. Each run takes only a
few pages. Run it once a day and the bot slowly gets every car.

Script: `scripts/crawl_queue.py` (plain Python, no extra package).
Table: `crawl_queue` in the same SQLite database as the bot
(`bot.db`) — same table and column names will be used in Supabase
later, so moving is easy. New cars are saved in the database AND
added to the seed list in `seed_data.py`, so the live bot gets them on
the next deploy. If a page fails (for example error 429), the run
stops at once, the page is marked failed, and it is tried again
next time. After 3 failed tries a page is left alone for a human.

Exact commands (run from the repo folder):

- Fill the queue with every stock page (reads page 1 to count cars):
  `python3 scripts/crawl_queue.py --fill`
- See how the queue is doing:
  `python3 scripts/crawl_queue.py --status`
- Crawl the next 10 pages (the daily run — this is the command the
  daily schedule will run):
  `python3 scripts/crawl_queue.py --pages 10`
- Crawl more pages, with a longer wait between them:
  `python3 scripts/crawl_queue.py --pages 20 --delay 5`

The script prints a summary at the end: `pages done=X cars added=Y
cars updated=Z pages failed=W`. The admin page shows the queue too
(pages waiting, done, failed, and the last 20 rows). The queue
worker runs on a schedule, NOT on Vercel — Vercel only shows the
cars, it never crawls. Note: the queue on Vercel starts empty,
because Vercel makes a fresh database each time it starts; the
real queue lives where the worker runs.

## Real cars and import rules (Nov 2026)

The bot's seed data is real data from afriditrading.com, not made up:

- **1,958 cars**: the 10 original demo cars + 1,948 real cars read
  from the stock pages 1–82 (24 cars per page, Nov 2026). The site
  has 38,236 cars on 1,594 pages, so this is a real sample of the
  newest listings, not the whole stock. Every car has a real FOB
  price and its real photo link; no price was invented. 927 of
  them have a real auction grade from the site (most cars have no
  grade at all — the bot never invents one). The listing pages
  show a fuel tag (Hybrid / Light Oil / Diesel) but no body-type
  field, so `body_type` holds the fuel tag.
- **77 countries' import rules**: max car age, port, shipping time,
  sailings, inspection and shipping line, read from
  afriditrading.com/import and each country page. 6 countries
  (Sudan, Tanzania, Togo, Uganda, Zambia, Zimbabwe) had their pages
  blocked, so only their age limit from the import index page is
  used. 7 Caribbean pages do not exist (Barbados, Belize, Saint
  Lucia, Dominica, Saint Vincent, Saint Kitts, Haiti — all 404).
  Sudan is left out: the site only says "See import rules".

The bot answers "import rules for <country>" for any of these 77
countries, and "show me cars under $<amount>" from the real cars.

## Unanswered questions — how the bot learns

1. A customer asks something the bot does not know. The bot saves
   the question as an open inquiry (with the customer, if signed
   in) and says so honestly.
2. The admin opens the admin panel, finds it under "Unanswered
   questions", types the answer and presses Save.
3. Saving does two things: it marks the inquiry "answered" and adds
   the question + answer to the Knowledge base (faqs table), and
   clears the FAQ cache — so the next customer who asks the same
   question gets the answer at once. The admin can also add or
   delete Knowledge base entries by hand.

## Supabase — the live database

When `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set (as environment
variables, never in code), the bot reads and writes Supabase project
`jlbapnqzntqlyjuqvtmq` instead of the local SQLite file — users,
cars, chats, messages, inquiries, invoices, shipments, import rules,
reviews, FAQs and the crawl queue. The first start seeds Supabase
from the same seed data (1,958 cars, 77 import rules, 20 FAQs) and
adds the sample shipment ATJ-1001, only adding what is missing.
When the two settings are not set, the bot uses SQLite, as before.
If Supabase is set but the startup test read fails (for example the
tables do not let the anon role use them yet — run the GRANTs below),
the bot keeps running on SQLite and says why on `/health`.

The Supabase tables need these grants for the anon role (run once
in Supabase Dashboard > SQL Editor):

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public
  TO anon, authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public
  TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO anon, authenticated;
```

Never put the key in code or GitHub.

## How I built this

1. I made the database first: 10 tables in SQLite, one file.
2. I added sample cars from afriditrading.com and sample import rules.
3. I wrote the chatbot: one function, `bot_reply`, that reads the question,
   finds keywords, and answers from the database or the knowledge base.
4. I made the website with Flask: one file, `app.py`, with short functions.
5. I made the pages with HTML and CSS, and the chat window with JavaScript.
   JavaScript sends the message to `/api/chat` without reloading the page.
6. I tested it: home page, car search, chat, invoice, tracking, admin.

## Technology

- Python + Flask (back end)
- HTML + CSS + JavaScript (front end)
- SQLite (database for the demo; Firebase for the live website)
