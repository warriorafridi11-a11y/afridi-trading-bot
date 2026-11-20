"""Seed data for the Afridi Trading Bot: the cars, import
rules and real FAQs. Kept in its own file only because
app.py got too big to deploy in one piece — the data is
exactly the same as before. Real cars from afriditrading.com
(stock pages 1-13, Nov 2026). Prices are FOB prices.
"""


# Sample cars, like the cars on afriditrading.com. Price is the FOB price.
# Real cars from afriditrading.com (stock pages 1-13, 308 cars, Nov 2026). The first 10 are the original demo cars.
# Price is the FOB price. body_type holds the fuel tag the listing shows (Hybrid / Light Oil / Diesel), because the listing shows no body-type field.
# Real cars from afriditrading.com (stock pages 1-13, Nov 2026).
# Compact form, one car per line: make|model|year|distance_km|
# price_fob|body_type|status. Empty distance means the listing
# showed no mileage. Price is the FOB price. body_type holds the
# fuel tag the listing shows (Hybrid / Light Oil / Diesel),
# because the listing shows no body-type field. The first 10 are
# the original demo cars.
# New cars also carry four more fields, after status:
# ref|auction_grade|image_url|condition_note. The ref is the
# website reference (e.g. AA35371). The grade is the auction
# grade from the site, or empty: most cars have no grade, and
# the bot never invents one. image_url is the main photo link.
# condition_note is empty: the site lists no condition note.
# The car list lives in small files (seed_cars_a.py, ...),
# so each file stays small enough to deploy. New cars go
# in the last file; see scripts/crawl_queue.py.
from seed_cars_a import CARS_A
from seed_cars_b import CARS_B
from seed_cars_c import CARS_C
from seed_cars_d import CARS_D


SAMPLE_CARS = CARS_A + CARS_B + CARS_C + CARS_D


def seed_car_rows():
    """Parse the compact SAMPLE_CARS strings into database rows.

    Old lines have 7 fields; new lines have up to 11. Returns
    11 values per car: make, model, year, distance_km, price_fob,
    body_type, status, ref, auction_grade, image_url,
    condition_note. Missing extra fields become None.
    """
    rows = []
    for line in SAMPLE_CARS:
        parts = line.split("|")
        make, model, year, km, price, body, status = parts[:7]
        extra = parts[7:] + [None] * (4 - len(parts[7:]))
        ref, grade, image, note = extra[:4]
        rows.append((make, model, int(year),
                     int(km) if km else None, int(price), body, status,
                     ref or None, grade or None, image or None,
                     note or None))
    return rows

# Sample import rules. These are simple demo rules, not legal advice.
# Import age limits from the website import page (afriditrading.com/import).
# 0 means no age limit on that page. These are simple demo rules,
# not legal advice — the full guide is on the website.
# Real import rules from afriditrading.com/import and the country pages (Nov 2026). 0 means no age limit, None means the website does not state an age limit. These are simple demo rules, not legal advice — the full guide is on the website.
SAMPLE_RULES = [
    ('Afghanistan', 0, 'Shipping: 16–26 Days (RoRo). Sailings: Monthly. Inspection: No Inspection Required. Line: ECL / NYK. Not stated on page: port.'),
    ('Angola', 5, 'Port: Luanda. Shipping: 24–36 Days (RoRo). Sailings: Monthly (RoRo). Inspection: PSI. Line: Waitara. Page states min. manufacturing year 2021.'),
    ('Antigua and Barbuda', 0, 'Port: Saint Johns. Shipping: 24–34 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Not stated on page: shipping line.'),
    ('Armenia', 0, 'Shipping: 34-46 Days. Sailings: Monthly. Line: MAERSK. Not stated on page: port, inspection.'),
    ('Bahamas', 10, 'Port: Freeport. Shipping: 24–39 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Line: CNC Japan. Manufacturing year 2016 or later (per page FAQ).'),
    ('Bahrain', 5, 'Shipping: 22–31 Days. Sailings: Weekly. Manufacturing year 2021 or later (per page FAQ). Not stated on page: port, inspection, shipping line.'),
    ('Bangladesh', 4, 'Port: Chittagong. Shipping: 19–24 Days (RoRo). Sailings: Monthly. Inspection: JAAI. Manufacturing year 2022 or later (per page FAQ). Not stated on page: shipping line.'),
    ('Benin', 0, "Port: Cotonou. Shipping: 34-44 Days. Sailings: Monthly (RoRo). Inspection: Required. Shipping line not stated on page (shown as '-')."),
    ('Bhutan', None, "Page shows no import-rule header fields (site index lists 'See import rules'); no age limit, port, shipping time, inspection or shipping line stated."),
    ('Botswana', 0, 'Port: Durban. Shipping: 24-34 Days. Sailings: Monthly (RoRo). Inspection: No Inspection. Line: Mediterranean Shipping Company. Landlocked; shipped via Durban, South Africa.'),
    ('Brunei', 3, 'Port: Muara Harbor. Shipping: 13–20 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Line: E&W Maritime. Manufacturing year 2023 or later (per page FAQ).'),
    ('Burkina Faso', 0, 'Port: Koudougou And Ouagadougou. Shipping: 28–36 Days (Container). Sailings: Weekly. Inspection: No Inspection. Line: Fesco Lines. Landlocked; destination shown as the inland cities Koudougou and Ouagadougou.'),
    ('Burundi', 0, 'Port: Mombasa. Shipping: 24-34 Days. Sailings: Monthly (RoRo). Inspection: No Inspection. Line: Keihin, MOL, Hoegh. Landlocked; shipped via Mombasa, Kenya.'),
    ('China', 10, 'Port: Tianjin Xin Gang. Shipping: 10–15 Days (Container). Sailings: Weekly. Line: COSCO. Manufacturing year 2016 or later (per page FAQ). Not stated on page: inspection.'),
    ('Comoros', None, "Port: Moroni. Shipping: 28–34 Days (Container). Sailings: Weekly. Age limit, inspection and shipping line not stated on page (all shown as '-')."),
    ('Cote Divoire', 5, "Port: Abidjan. Shipping: 34–46 Days (RoRo). Sailings: 34-46 Days. Line: OMA Côte d'Ivoire. Inspection not stated on page (shown as '-'); vessel schedule field on the page literally shows '34-46 Days' rather than a frequency; min. manufacturing year 2021."),
    ('Dominican Republic', 10, 'Port: Santo Domingo. Shipping: 24–36 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Manufacturing year 2016 or later (per page FAQ). Not stated on page: shipping line.'),
    ('Egypt', 1, 'Port: Al Iskandariyh (Alexandria). Shipping: 21–28 Days (Container). Sailings: Weekly. Inspection: No Inspection. Line: United Arab Shipping Agencies. Page states min. manufacturing year 2025.'),
    ('Equatorial Guinea', 10, "Shipping: 34-44 Days. Sailings: Monthly. Inspection: Fiche de Demande d’Inspection. Destination port not stated on page; shipping line not stated (shown as '-'); min. manufacturing year 2016."),
    ('Ethiopia', 0, "Port: Djibouti. Shipping: 21–30 Days (Container). Sailings: Weekly. Inspection: No Inspection. Landlocked; shipped via Djibouti; shipping line not stated on page (shown as '-')."),
    ('Gabon', 3, "Port: Libreville. Shipping: 34–44 Days (RoRo). Sailings: Monthly. Inspection: PROGEC. Shipping line not stated on page (shown as '-'); min. manufacturing year 2023."),
    ('Gambia', 8, "Port: Banjul. Shipping: 26–34 Days (Container). Sailings: Weekly. Inspection: ASYCUDA. Shipping line not stated on page (shown as '-'); min. manufacturing year 2018."),
    ('Georgia', 0, 'Port: Poti. Shipping: 34–46 Days (Container). Sailings: Monthly. Inspection: No Inspection. Line: MAERSK / CMA CGM.'),
    ('Ghana', 10, 'Port: Tema. Shipping: 34–44 Days (RoRo). Sailings: Monthly. Inspection: PVoC. Line: Apex Shipping. Verified against known data; matches (max 10 years, TEMA, 34-44 days RoRo, monthly, PVoC, Apex Shipping); min. manufacturing year 2016.'),
    ('Grenada', 0, 'Port: Saint George. Shipping: 24–39 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Not stated on page: shipping line.'),
    ('Guyana', 8, 'Port: Georgetown. Shipping: 24–34 Days (RoRo). Sailings: Less Than Bi-Monthly (RoRo). Inspection: ATJ Inspection. Line: Yuwa, Hoegh, MOL. Manufacturing year 2018 or later (per page FAQ).'),
    ('Hong Kong', 7, 'Port: Hong Kong. Shipping: 9–14 Days (RoRo). Sailings: Fortnightly. Inspection: No Inspection. Line: ZIM / OOCL. Manufacturing year 2019 or later (per page FAQ).'),
    ('India', 3, 'Port: Chennai (Madras). Shipping: 19–24 Days (RoRo). Sailings: Monthly. Inspection: Roadworthiness. Line: Naval Docks. Manufacturing year 2023 or later (per page FAQ).'),
    ('Indonesia', None, 'Port: Tanjung Benete. Shipping: 11–23 Days (RoRo). Sailings: Monthly. Not stated on page: year restriction, inspection, shipping line.'),
    ('Iran', 3, 'Port: Bandar Abbas. Shipping: 29–38 Days (RoRo). Sailings: Bi-Monthly. Manufacturing year 2023 or later (per page FAQ). Not stated on page: inspection, shipping line.'),
    ('Iraq', 2, 'Port: Umm Qasr. Shipping: 29–34 Days (Container). Sailings: Weekly. Manufacturing year 2024 or later (per page FAQ). Not stated on page: inspection, shipping line.'),
    ('Jamaica', 6, 'Port: Kingston. Shipping: 24–34 Days (RoRo). Sailings: Monthly. Inspection: Pre-Shipment Inspection. Line: CNC Japan. Manufacturing year 2020 or later (per page FAQ).'),
    ('Jordan', 10, 'Port: Al Aqabah. Shipping: 24–33 Days (Container). Sailings: Weekly. Manufacturing year 2016 or later (per page FAQ). Not stated on page: inspection, shipping line.'),
    ('Kazakhstan', 5, 'Shipping: 24–26 Days (Container). Sailings: Weekly. Manufacturing year 2021 or later (per page FAQ). Not stated on page: port, inspection, shipping line.'),
    ('Kyrgyzstan', 10, 'Port: Bishkek. Shipping: 34–36 Days (Container). Sailings: Weekly. Inspection: No Inspection. Manufacturing year 2016 or later (per page FAQ). Not stated on page: shipping line.'),
    ('Laos', 0, 'Port: Port of Laos. Inspection: No Inspection. Not stated on page: shipping time, vessel schedule, shipping line.'),
    ('Lebanon', 8, 'Port: Bayrut. Shipping: 34–46 Days (Container). Sailings: Monthly. Manufacturing year 2018 or later (per page FAQ). Not stated on page: inspection, shipping line.'),
    ('Lesotho', 0, 'Shipping: 24–34 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Line: K Line. Destination port not stated on page (landlocked; no port named).'),
    ('Liberia', 10, 'Port: Monrovia. Shipping: 39–49 Days (RoRo). Sailings: Monthly. Inspection: BIVAC. Line: Umarco Shipping. Min. manufacturing year 2016.'),
    ('Libya', 5, "Port: Mina Tarabulus (Tripoli). Shipping: 29–40 Days (Container). Sailings: Weekly. No inspection field or inspection FAQ on the page; shipping line not stated (shown as '-'); min. manufacturing year 2021."),
    ('Macau', None, 'Port: Macau. Shipping: 7–10 Days (Container). Sailings: Weekly. Not stated on page: year restriction, inspection, shipping line.'),
    ('Madagascar', None, "Port: Tamatave. Shipping: 34–44 Days (RoRo). Sailings: Monthly. Inspection: BSC / CTN. Age limit not stated on page (shown as '-'); shipping line not stated (shown as '-')."),
    ('Malawi', 0, "Port: Dar Es Salaam. Shipping: 24–34 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Landlocked; shipped via Dar es Salaam, Tanzania; shipping line not stated on page (shown as '-')."),
    ('Malaysia', 5, 'Port: Penang. Shipping: 9–13 Days (Container). Sailings: Weekly. Manufacturing year 2021 or later (per page FAQ). Not stated on page: inspection, shipping line.'),
    ('Maldives', 0, 'Port: Male. Shipping: 21–30 Days. Sailings: Weekly. Inspection: No Inspection. Line: Asia Forwarding.'),
    ('Mauritania', 8, "Port: Nouakchott. Shipping: 34–44 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Shipping line not stated on page (shown as '-'); min. manufacturing year 2018."),
    ('Mauritius', 4, 'Port: Port Louis. Shipping: 19–24 Days (RoRo). Sailings: Monthly. Inspection: JEVIC / JAAI. Line: PAS Mauritius. Min. manufacturing year 2022.'),
    ('Mongolia', 0, 'Port: Ulaanbaatar. Shipping: 13–20 Days (Container). Sailings: Weekly. Inspection: No Inspection. Line: Shipping Line Mongolia.'),
    ('Mozambique', 0, "Port: Maputo. Shipping: 29–34 Days (RoRo). Sailings: Monthly. Inspection: Intertek. Shipping line not stated on page (shown as '-')."),
    ('Myanmar', 5, 'Port: Yangon. Shipping: 13–22 Days (Container). Sailings: Weekly. Inspection: No Inspection. Line: S.R Shipping Myanmar. Manufacturing year 2021 or later (per page FAQ).'),
    ('Namibia', 12, 'Port: Walvis Bay. Shipping: 29–36 Days (Container). Sailings: Weekly. Inspection: No Inspection. Line: Manica Group. Min. manufacturing year 2014.'),
    ('Nigeria', 15, 'Port: Lagos. Shipping: 34–44 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Line: 3MO Shipping. Min. manufacturing year 2011.'),
    ('Oman', 10, 'Port: Muscat. Shipping: 29–34 Days. Sailings: Less Than Bi-Monthly. Manufacturing year 2016 or later (per page FAQ). Not stated on page: inspection, shipping line.'),
    ('Pakistan', 3, 'Port: Karachi. Shipping: 14–24 Days (RoRo). Sailings: Monthly. Inspection: Not Required. Line: Al-Hamd International. Manufacturing year 2023 or later (per page FAQ).'),
    ('Philippines', 0, 'Port: Manila. Shipping: 5–8 Days (Container). Sailings: Weekly. Inspection: PIA. Not stated on page: shipping line.'),
    ('Qatar', 5, 'Port: Doha. Shipping: 20–29 Days (Container). Sailings: Weekly. Inspection: Fahes. Manufacturing year 2021 or later (per page FAQ). Not stated on page: shipping line.'),
    ('Rwanda', 0, 'Port: Mombasa. Shipping: 24–34 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Line: Hyundai Glovis. Landlocked; shipped via Mombasa, Kenya.'),
    ('Saudi Arabia', 5, 'Port: Dammam. Shipping: 34–46 Days (Container). Sailings: Bi-Monthly. Inspection: No Inspection. Manufacturing year 2021 or later (per page FAQ). Not stated on page: shipping line.'),
    ('Senegal', 8, 'Port: Dakar. Shipping: 34–44 Days (RoRo). Sailings: Monthly. No inspection or shipping line field on the page; min. manufacturing year 2018.'),
    ('Seychelles', 3, 'Port: Victoria. Shipping: 28–39 Days (Container). Sailings: Monthly. No inspection or shipping line field on the page; min. manufacturing year 2023.'),
    ('Sierra Leone', 0, 'Port: Freetown. Shipping: 34–45 Days (Container). Sailings: Weekly. Inspection: No Inspection. Shipping line not stated on the page.'),
    ('Singapore', 3, 'Port: Keppel (East Singapore). Shipping: RoRo (09-14 Days). Sailings: Fortnightly. Inspection: No Inspection. Line: Samudera Shipping Line Pte Ltd.. Manufacturing year 2023 or later (per page FAQ).'),
    ('Somalia', None, "Port: Berbera. Shipping: 36–46 Days (Container). Sailings: Weekly. No age restriction stated on the page (import index says 'See import rules'); no inspection or shipping line field on the page."),
    ('South Africa', 0, 'Port: Durban. Shipping: 24–34 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Line: Keihin.'),
    ('South Korea', 0, 'Port: Busan. Shipping: 20–30 Days (RoRo). Sailings: Weekly. Inspection: No Inspection. Line: Hyundai Merchant Marine.'),
    ('South Sudan', 0, 'Port: Mombasa. Shipping: 24–36 Days (RoRo). Sailings: Monthly. Inspection: EAA. Line: Hyundai Glovis. Landlocked; shipped via Mombasa, Kenya.'),
    ('Sri Lanka', 3, 'Port: Colombo. Shipping: 14–24 Days (RoRo). Sailings: Fortnightly. Inspection: JAAI. Line: K-Line / MOL. Manufacturing year 2023 or later (per page FAQ).'),
    ('Taiwan', 10, 'Port: Keelung. Shipping: 5–9 Days. Line: ZIM. Manufacturing year 2016 or later (per page FAQ). Not stated on page: vessel schedule, inspection.'),
    ('Tanzania', 0, 'No age limit, from the import index page. Port, shipping time and inspection were not read — the country page could not be opened.'),
    ('Thailand', 0, 'Port: Bangkok. Shipping: 14–19 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Line: Thailand Star Shipping.'),
    ('Togo', 0, 'No age limit, from the import index page. Port, shipping time and inspection were not read — the country page could not be opened.'),
    ('Trinidad and Tobago', 4, 'Port: Port of Spain. Shipping: 24–34 Days (RoRo). Sailings: Monthly. Inspection: No Inspection. Line: CNC Japan. Manufacturing year 2022 or later (per page FAQ).'),
    ('Turkey', 0, 'Port: Istanbul. Shipping: 29-36 Days. Sailings: Monthly. Inspection: TÜVTURK. Line: ZIM Integrated Shipping Services Ltd.'),
    ('Uganda', 15, 'Age limit from the import index page. Port, shipping time and inspection were not read — the country page could not be opened.'),
    ('Vietnam', 5, 'Port: Ho Chi Minh City. Shipping: 10–17 Days (Container). Sailings: Weekly. Line: Ben Line Agencies. Manufacturing year 2021 or later (per page FAQ). Not stated on page: inspection.'),
    ('Zambia', 0, 'No age limit, from the import index page. Port, shipping time and inspection were not read — the country page could not be opened.'),
    ('Zimbabwe', 10, 'Age limit from the import index page. Port, shipping time and inspection were not read — the country page could not be opened.'),
]


# Real buyer questions and answers, taken from afriditrading.com
# (home page, How to Buy, FAQs, Payment Information, Shipping
# Information and import pages). Short answers, simple words.
# Each FAQ has keywords: the bot checks these first.
SAMPLE_FAQS = [
    ("How do I buy a car?",
     "5 easy steps: 1. Search your car. 2. Inquire. 3. Get your invoice. "
     "4. Pay. 5. Shipment. You can buy from stock in Japan, UK, Thailand "
     "and Korea, or buy a pre-shipped car.",
     "buying", ("how to buy", "how do i buy", "buying steps")),
    ("How do I pay?",
     "Pay by telegraphic transfer to our company bank account in Japan, "
     "or by Visa, Mastercard or PayPal. We also take WISE business "
     "account payments. The beneficiary is always Afridi Trading. Never "
     "pay to a person and never use Western Union.",
     "payment", ("how do i pay", "how to pay", "payment method")),
    ("Can I pay with a card?",
     "Yes. We take Visa, Mastercard and PayPal, as well as bank transfer "
     "and WISE. Bank fees are paid by the buyer.",
     "payment", ("pay with a card", "credit card", "visa", "mastercard", "paypal")),
    ("What is your refund policy?",
     "The auction security deposit is 100% refundable. If you cancel a "
     "purchase order, you may need to pay the costs already spent, "
     "because we may have to resell the car. Ask sales before you pay.",
     "refund", ("refund", "cancel my order", "cancel purchase")),
    ("How long does shipping take?",
     "Delivery usually takes 4 to 8 weeks. The exact time depends on the "
     "shipping schedule. Once your car is fully paid, we ship it on the "
     "earliest available vessel.",
     "shipping", ("how long", "delivery time", "shipping take")),
    ("How much is freight?",
     "Freight depends on the car size and the port, so there is no one "
     "fixed freight price. The exact freight is written on your invoice. "
     "Tell me your country for a sample freight price.",
     "freight", ("freight", "shipping cost")),
    ("Is shipping insured?",
     "Yes. Shipping is insured, with full marine transit cover. In this "
     "demo the delivered price adds $100 for insurance.",
     "insurance", ("insurance", "insured")),
    ("What documents do I get?",
     "You get a proforma invoice first. After you pay, we ship the car "
     "and courier the original B/L (bill of lading) to you, so you can "
     "clear the car at your port.",
     "documents", ("document", "bill of lading", "b/l", "papers")),
    ("How do I collect my car at the port?",
     "You collect the car at your destination port. Bring the original "
     "B/L and your ID to clear it. We handle the auction, export papers "
     "and shipping.",
     "port", ("collect", "pick up my car", "pickup")),
    ("What does FOB mean?",
     "FOB means the price in Japan. Extra costs are freight, clearance, "
     "import duty, registration and compliance fees. C&F means FOB plus "
     "freight. CIF means FOB plus freight plus insurance.",
     "price", ("fob", "cif", "c&f", "what does fob")),
    ("What is an auction grade?",
     "Auction grades go from 3 to 5 and S. Grade 5 and S are the best. "
     "Grade 4 is good. Grade 3.5 is fair. Grade R means the car was "
     "repaired after an accident.",
     "grade", ("auction grade",)),
    ("What is the auction sheet?",
     "The auction sheet shows the car's condition, grade and marks. All "
     "cars go through a full inspection to make sure they match the "
     "sheet. Ask me about one grade, for example: what is grade 4?",
     "grade", ("auction sheet",)),
    ("Can I bid at the Japan auctions?",
     "Yes. Register, talk to a sales representative, and pay a security "
     "deposit (100% refundable) to start bidding. You bid up to your "
     "account credit limit. We are members of all auction houses in "
     "Japan, with about 100,000 cars each week.",
     "auction", ("bid", "auction")),
    ("How many cars do you have?",
     "We have over 2,000 cars in our regular stock, and about 100,000 "
     "cars each week through the Japan auctions. Tell me a make or a "
     "budget and I will show you cars.",
     "stock", ("how many cars", "how much stock")),
    ("Are there hidden charges?",
     "No. There are no registration fees or hidden charges, and sign up "
     "is free. The buyer pays the bank fees.",
     "payment", ("hidden charge", "hidden fee", "registration fee")),
    ("Do you sell left-hand drive cars?",
     "Left-hand drive cars are rare in Japan, but we can find them in "
     "our Korean and American stock. Ask us for the model you want.",
     "cars", ("left hand", "lhd")),
    ("How do I know you are real and not a scam?",
     "Verify any person at afriditrading.com/verify. Every real "
     "representative has a verification card with a QR code, and their "
     "WhatsApp number is on our live staff list. Our emails only end in "
     "@afriditrading.com, and our staff never take payments personally.",
     "trust", ("scam", "verify", "you are real", "fake", "not a scam")),
    ("What is your WhatsApp number?",
     "WhatsApp sales: +81 80 5173 0786 or +81 70 4457 0584. Customer "
     "support: +81 80 7256 3364. Office hours are Monday to Friday 9 to "
     "6, Saturday 9 to 4, Japan time.",
     "contact", ("whatsapp",)),
    ("Do you ship to my country?",
     "We ship to 126 destinations. Tell me your country and I will tell "
     "you the import age limit and the delivered price to your port.",
     "shipping", ("ship to my country", "do you ship")),
    ("How do I track my car?",
     "Send your tracking number, for example: track ATJ-1001. Once your "
     "car is fully paid, we ship it on the earliest available vessel.",
     "tracking", ("track my car", "where is my car")),
]
