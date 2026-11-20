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

## Pages

- `/` — home page with the chat window
- `/cars` — car list, search by budget and make
- `/invoice/<car id>` — invoice for one car
- `/track` — track a shipment, try `ATJ-1001`
- `/admin` — admin panel: chats, cars, invoices, shipments

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
