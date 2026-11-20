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

## Supabase — not connected yet

The live bot still uses SQLite. On Vercel the SQLite file lives in
`/tmp`, so it is lost when the server restarts — user accounts and
chat history will only be permanent once the app is connected to the
Supabase project `jlbapnqzntqlyjuqvtmq` (tables already made there).
That needs the Supabase anon key from the dashboard
(Settings > API > anon public key), set as `SUPABASE_URL` and
`SUPABASE_ANON_KEY` on Vercel. Never put the key in code or GitHub.

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
