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
from datetime import datetime

import smtplib
from email.message import EmailMessage

from flask import (Flask, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

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
# Real cars from afriditrading.com (stock pages 1-13, 308 cars, Nov 2026). The first 10 are the original demo cars.
# Price is the FOB price. body_type holds the fuel tag the listing shows (Hybrid / Light Oil / Diesel), because the listing shows no body-type field.
# Real cars from afriditrading.com (stock pages 1-13, Nov 2026).
# Compact form, one car per line: make|model|year|distance_km|
# price_fob|body_type|status. Empty distance means the listing
# showed no mileage. Price is the FOB price. body_type holds the
# fuel tag the listing shows (Hybrid / Light Oil / Diesel),
# because the listing shows no body-type field. The first 10 are
# the original demo cars.
SAMPLE_CARS = [
    "Toyota|Aqua S|2016|140000|1600|Hybrid|In stock",
    "Toyota|Aqua S|2014|172000|1500|Hybrid|In stock",
    "Toyota|Vitz F|2011|255000|2750|Hatchback|In stock",
    "Toyota|Vitz F|2014|32000|4000|Hatchback|In stock",
    "Toyota|Voxy Hybrid X|2017|212000|6500|Minivan|In stock",
    "Toyota|Corolla Axio|2017|128000|3300|Sedan|In stock",
    "Honda|Vezel|2018|98000|4550|SUV|In stock",
    "Honda|Fit|2016|115000|1150|Hatchback|In stock",
    "Suzuki|Swift XG|2014|99000|2000|Hatchback|In stock",
    "Toyota|Sienta Hybrid G|2016|277000|3100|Minivan|In stock",
    "Suzuki|Solio MV|2021|33000|10550|Hybrid|In stock",
    "Honda|Odyssey Absolute EX|2023|14000|31050|Hybrid|In stock",
    "Suzuki|Solio SZ|2022|6000|12350|Hybrid|In stock",
    "Suzuki|Solio MV|2021|49000|10350|Hybrid|In stock",
    "Suzuki|Solio MZ|2024|20000|14800|Hybrid|In stock",
    "Suzuki|Solio MV|2025||16650|Hybrid|In stock",
    "Suzuki|Solio MX|2024|15000|10700|Hybrid|In stock",
    "Honda|Odyssey Absolute EX|2024|24000|31150|Hybrid|In stock",
    "Honda|Odyssey Absolute EX|2021|25000|25700|Hybrid|In stock",
    "Suzuki|Solio MV|2022|36000|11950|Hybrid|In stock",
    "Honda|Odyssey Absolute EX|2025|11000|32150|Hybrid|In stock",
    "Honda|Odyssey Absolute|2022|72000|19050|Hybrid|In stock",
    "Suzuki|Solio MV|2024|16000|11300|Hybrid|In stock",
    "Honda|Odyssey Absolute EX|2022|27000|26050|Hybrid|In stock",
    "Suzuki|Solio MZ|2021|36000|8600||In stock",
    "Suzuki|Solio MV|2021|3000|12350|Hybrid|In stock",
    "Honda|Odyssey Absolute EX|2023|25000|30700|Hybrid|In stock",
    "Nissan|Skyline Nismo|2024|18000|40400||In stock",
    "Suzuki|Solio MV|2022|31000|12150|Hybrid|In stock",
    "Honda|Odyssey e:HEV Absolute EX|2022|20000|26800|Hybrid|In stock",
    "Suzuki|Solio MV|2022|34000|12300|Hybrid|In stock",
    "Suzuki|Solio MV|2018|14000|9450|Hybrid|In stock",
    "Honda|Odyssey Absolute EX|2021|40000|22150|Hybrid|In stock",
    "Toyota|Voxy S-Z|2024|16000|18800||In stock",
    "Toyota|Voxy ZS Sparkle2|2016|107000|7600||In stock",
    "Toyota|Raize Z|2020|49000|10500||In stock",
    "Honda|Vezel Z Honda Sensing|2018|41000|8200|Hybrid|In stock",
    "Honda|Freed air|2024|18000|15600|Hybrid|In stock",
    "Honda|Freed closter|2024|19000|15800|Hybrid|In stock",
    "Honda|Vezel Hybrid Z Honda Sensing|2018|73000|8800|Hybrid|In stock",
    "Toyota|Raize Z|2020|51000|8100||In stock",
    "Toyota|Voxy ZS Sparkle|2018|71000|13100|Hybrid|In stock",
    "Honda|Fit Home|2022|34000|7900|Hybrid|In stock",
    "Honda|Freed G black style|2022|39000|9400|Hybrid|In stock",
    "BMW|X1 xDrive18d x line|2019|37000|9000|Light Oil|In stock",
    "Toyota|Prado TX L package matte black Ed|2022|26000|25900||In stock",
    "Lexus|UX F sports|2023|20000|19100||In stock",
    "Toyota|Corolla Cross Z|2025|13000|16800|Hybrid|In stock",
    "Lexus|RX elegant tourer|2022|13000|25300|Hybrid|In stock",
    "Toyota|Voxy Hybrid S-Z|2022|38000|18500|Hybrid|In stock",
    "Honda|Freed e:HEV air|2024|13000|16200|Hybrid|In stock",
    "Lexus|ES F sports|2019|47000|20600|Hybrid|In stock",
    "Toyota|Crown Sport Z|2023|27000|24700|Hybrid|In stock",
    "Toyota|Hiace Van DX GL package|2022|58000|15900|Light Oil|In stock",
    "Audi|Q3 35 TFSI S line|2022|28000|18100|Hybrid|In stock",
    "Toyota|Corolla Cross Z|2023|57000|15800|Hybrid|In stock",
    "Honda|Vezel Z|2022|46000|13500|Hybrid|In stock",
    "Toyota|Raize Z|2025|8000|13500|Hybrid|In stock",
    "Honda|Fit F package|2015|74000|3400|Hybrid|In stock",
    "Toyota|Voxy Hybrid S-Z|2023|52000|19100|Hybrid|In stock",
    "Toyota|Voxy S-Z|2023|26000|20000|Hybrid|In stock",
    "Honda|Vezel Z|2021|47000|12400|Hybrid|In stock",
    "Honda|Stepwgn Spada Cool Spirit H Sensing|2017|31000|14500||In stock",
    "Toyota|Crown Sport Z E-Four|2024|20000|26400|Hybrid|In stock",
    "BMW|X4 xDrive30i M Sport|2019|31000|20500||In stock",
    "Toyota|Raize Z|2023|33000|11500||In stock",
    "Honda|Stepwgn premium line|2024|27000|20300|Hybrid|In stock",
    "Lexus|RX F sports|2021|56000|25300|Hybrid|In stock",
    "Toyota|Voxy S-Z|2023|20000|19100||In stock",
    "Honda|Vezel RS Honda Sensing|2018|82000|7800|Hybrid|In stock",
    "Toyota|Voxy ZS Sparkle2|2019|36000|17000||In stock",
    "Toyota|Corolla Cross Z|2024|26000|20000|Hybrid|In stock",
    "Toyota|Voxy S-Z|2023|28000|19400||In stock",
    "Lexus|NX Version L|2023|41000|27800|Hybrid|In stock",
    "Toyota|Voxy ZS Sparkle|2016|76000|8500||In stock",
    "Toyota|Voxy S-Z|2022|31000|18700||In stock",
    "Honda|Vezel RS Honda Sensing|2019|39000|9500|Hybrid|In stock",
    "Lexus|NX F sports|2022|22000|30300|Hybrid|In stock",
    "Toyota|RAV4 adventure|2025|19000|22600|Hybrid|In stock",
    "Honda|Vezel X Honda Sensing|2018|61000|8100|Hybrid|In stock",
    "Honda|Stepwgn premium line|2022|28000|20600|Hybrid|In stock",
    "Toyota|Corolla Cross Hybrid Z|2024|29000|15900|Hybrid|In stock",
    "BMW|X1 xDrive18d M Sport|2017|49000|8100|Light Oil|In stock",
    "Lexus|NX F sports|2025|18000|34400|Hybrid|In stock",
    "Honda|Freed G Honda Sensing|2021|40000|8800||In stock",
    "Toyota|RAV4 G|2023|38000|16200||In stock",
    "Toyota|Yaris Cross Z|2024|13000|14000|Hybrid|In stock",
    "Honda|Vezel Z|2021|33000|12800|Hybrid|In stock",
    "BMW|X1 xDrive18d M Sport|2020|45000|13500|Light Oil|In stock",
    "Audi|Q5 40 TDI Quattro S line|2021|32000|17900|Hybrid|In stock",
    "BMW|X3 xDrive20d M Sport|2018|11000|18200|Light Oil|In stock",
    "Lexus|NX F sports|2015|103000|9000|Hybrid|In stock",
    "Honda|Fit L Honda Sensing|2018|48000|5700|Hybrid|In stock",
    "Honda|Freed G Honda Sensing|2018|86000|4600||In stock",
    "Honda|Freed G|2023|29000|10900|Hybrid|In stock",
    "Lexus|RX F sports|2017|59000|15900||In stock",
    "Toyota|Yaris Cross Z Adventure|2023|66000|11900|Hybrid|In stock",
    "Lexus|RX F Sports Performance|2024|36000|41500|Hybrid|In stock",
    "Toyota|Yaris Cross Z|2020|39000|11800|Hybrid|In stock",
    "Toyota|Hilux Z|2023|10000|22100|Light Oil|In stock",
    "Lexus|Lbx elegant|2025|14000|22900|Hybrid|In stock",
    "Toyota|Hiace Wagon GL|2022|26000|25700||In stock",
    "Toyota|Markx 250G|2013|82000|5350||In stock",
    "Toyota|Markx 250G|2017|82000|7500||In stock",
    "Toyota|Crown RS Limited|2020|98000|17750|Hybrid|In stock",
    "Toyota|Prius Phv S|2019|70000|10000|Hybrid|In stock",
    "Toyota|Markx premium|2016|21000|9650||In stock",
    "Toyota|Markx 250G|2014|36000|9000||In stock",
    "Toyota|Prius Phv A Premium|2019|48000|15150|Hybrid|In stock",
    "Toyota|Crown RS Advance|2018|45000|24300|Hybrid|In stock",
    "Toyota|Crown RS Advance|2018|83000|19650||In stock",
    "Toyota|Hiace Wagon Grand Cabin|2025|5000|28950||In stock",
    "Toyota|Crown RS Advance|2018|55000|24300|Hybrid|In stock",
    "Toyota|Crown RS Advance|2019|41000|22150|Hybrid|In stock",
    "Toyota|Crown RS Advance|2018|44000|23550|Hybrid|In stock",
    "Toyota|Hiace Wagon GL|2026||27850||In stock",
    "Toyota|Markx 250G|2012|89000|9250||In stock",
    "Toyota|Crown RS|2018|67000|16650|Hybrid|In stock",
    "Toyota|Hiace Wagon bus|2025|1000|35000||In stock",
    "Toyota|Markx 250G|2012|67000|3550||In stock",
    "Toyota|Crown SC package|2018|43000|19150|Hybrid|In stock",
    "Toyota|Prius Phv Z|2023|13000|20700|Hybrid|In stock",
    "Toyota|Hiace Wagon GL|2026||27500||In stock",
    "Toyota|Crown RS Advance|2019|63000|23550|Hybrid|In stock",
    "Toyota|Crown RS|2018|91000|17550|Hybrid|In stock",
    "Toyota|Crown RS Limited|2020|80000|22550|Hybrid|In stock",
    "Toyota|Crown RS|2018|65000|18950|Hybrid|In stock",
    "Toyota|Crown G|2019|49000|22550|Hybrid|In stock",
    "Toyota|Crown RS|2020|52000|24300|Hybrid|In stock",
    "Toyota|Crown RS Advance|2018|64000|21800|Hybrid|In stock",
    "Toyota|Crown RS Advance|2022|51000|26950|Hybrid|In stock",
    "Toyota|Hiace Van Super GL|2022|109000|18550|Diesel|In stock",
    "Toyota|Harrier Z|2021|28000|22500||In stock",
    "Toyota|Hiace Van Super GL|2025|18000|31300|Diesel|In stock",
    "Toyota|Harrier G|2024|12000|22150||In stock",
    "Toyota|Harrier G|2021|57000|17850|Hybrid|In stock",
    "Toyota|Harrier G|2025|12000|22000||In stock",
    "Toyota|Hiace Van Super GL|2021|134000|25550|Diesel|In stock",
    "Toyota|Harrier Z|2021|45000|21650|Hybrid|In stock",
    "Toyota|Harrier G|2021|52000|17700||In stock",
    "Toyota|Harrier S|2023|24000|18950||In stock",
    "Toyota|Harrier G|2025|13000|21050||In stock",
    "Toyota|Harrier Z|2023|15000|23950|Hybrid|In stock",
    "Toyota|Harrier Z|2020|63000|18500|Hybrid|In stock",
    "Toyota|Harrier Z|2024|28000|24300||In stock",
    "Toyota|Harrier Z|2023|24000|25000||In stock",
    "Toyota|Harrier G|2025|18000|21950||In stock",
    "Toyota|Harrier G|2024|18000|21450||In stock",
    "Toyota|Harrier Z|2020|34000|22650|Hybrid|In stock",
    "Toyota|Harrier G|2021|30000|18850||In stock",
    "Toyota|Hiace Van DX|2020|76000|15950|Diesel|In stock",
    "Toyota|Hiace Van Super GL|2020|51000|25000|Diesel|In stock",
    "Toyota|Harrier Z|2023|24000|24650||In stock",
    "Toyota|Hiace Van Super GL|2021|113000|25300|Diesel|In stock",
    "Toyota|Harrier Z|2021|19000|25000|Hybrid|In stock",
    "Honda|Vezel G|2021|38000|14000||In stock",
    "Audi|A1 25TFSI Advanced Adda|2022|17000|11000||In stock",
    "Mercedes-Benz|E Class E200 coupe sports 360|2019|31000|18000||In stock",
    "BMW|1 Series 118d M Sports One-Owner Car|2022|19000|14000|Light Oil|In stock",
    "Mercedes-Benz|A Class A200d AMG line cleanliness|2022|23000|15000|Light Oil|In stock",
    "Mercedes-Benz|C Class C180|2017|41000|16000||In stock",
    "BMW|5 Series 523d xDriveM Sports Ed|2021|39000|24000|Light Oil|In stock",
    "Mercedes-Benz|Cla CLA200d AMG line clean|2019|37000|16000|Light Oil|In stock",
    "Mercedes-Benz|Cla CLA180 Shooting brake|2016|40000|7000||In stock",
    "Audi|A3 30TFSI S line navigation bag|2022|10000|17000||In stock",
    "Mercedes-Benz|A Class A200d|2020|31000|11000|Light Oil|In stock",
    "BMW|X1 xDrive 18d M Sports 4W|2021|38000|14000|Light Oil|In stock",
    "BMW|2 Series 218d Grand Coupe M Sports|2023|27000|16000|Light Oil|In stock",
    "Audi|A4 35TDI S line one owner car semi|2021|35000|17000|Light Oil|In stock",
    "BMW|2 Series 218d Grand Coupe M Sports|2021|29000|12000|Light Oil|In stock",
    "Audi|A3 Sports bag 1.4TFSI sport|2018|33000|9000||In stock",
    "BMW|4 Series 420i|2020|27000|20000||In stock",
    "Audi|A5 40TDI Kuturo S line one owner|2021|33000|20000|Light Oil|In stock",
    "Audi|Q2 35TDI Advanced Navigation TV|2022|24000|15000|Light Oil|In stock",
    "BMW|3 Series 320d M Sports One-Owner Car|2015|48000|7000|Light Oil|In stock",
    "BMW|3 Series 320d Touring M Sports Clear|2016|24000|12000|Light Oil|In stock",
    "Mercedes-Benz|E Class Wagon E220d Station Wagon Ban|2018|30000|18000|Light Oil|In stock",
    "BMW|2 Series 218d Grant Aller M Sports|2018|49000|8000|Light Oil|In stock",
    "Mercedes-Benz|Cla CLA200d Shooting Brake|2020|19000|14000|Light Oil|In stock",
    "BMW|1 Series 118d M Sports One-Owner Car|2017|36000|7000|Light Oil|In stock",
    "Mercedes-Benz|A Class A200d Sedan AMG Line Clear|2021|22000|14000|Light Oil|In stock",
    "BMW|X2 xDrive 18d M Sports 4|2019|43000|10000|Light Oil|In stock",
    "Mercedes-Benz|C Class C220d AMG La|2021|24000|24000|Light Oil|In stock",
    "Mercedes-Benz|B Class B200d AMG line one-owner car|2022|33000|15000|Light Oil|In stock",
    "BMW|2 Series 218d grand coupe play ete|2020|22000|12000|Light Oil|In stock",
    "Mercedes-Benz|V Class V220d Sports Navigation TV 36|2017|20000|22000|Light Oil|In stock",
    "BMW|X3 xDrive 20i M Sports 4W|2015|35000|9000|Light Oil|In stock",
    "Audi|A1 25TFSI S line half leather|2020|34000|12000||In stock",
    "Lexus|NX NX350h|2024|16000|27000|Hybrid|In stock",
    "Mercedes-Benz|Cls CLS220d Sports Exclusive|2020|67000|19000|Light Oil|In stock",
    "Lexus|ES ES300h version L|2019|154000|14000|Hybrid|In stock",
    "BMW|X5 xDrive 40d M Sports|2024|15000|43000|Hybrid|In stock",
    "BMW|X3 20d xDrive M Sports|2024|14000|32000|Hybrid|In stock",
    "BMW|X2 xDrive 20d M Sports|2025|6000|28000|Hybrid|In stock",
    "BMW|3 Series 320d Touring Luxury|2016|50000|8000|Light Oil|In stock",
    "BMW|5 Series 530e M sports edition|2021|25000|20000|Hybrid|In stock",
    "BMW|3 Series 318i Touring M Sports|2021|30000|15000||In stock",
    "Mercedes-Benz|Cls CLS220d Sports Exclusive|2018|41000|22000|Light Oil|In stock",
    "Lexus|NX NX200t F sport late specification|2015|86000|11000||In stock",
    "Toyota|Voxy 2.0ZS Kira 7-seater|2016|111000|6000||In stock",
    "Honda|Fit Basic|2020|103000|5000||In stock",
    "BMW|4 Series 420i coupe luxury|2015|75000|5000||In stock",
    "BMW|2 Series 218iActive Tour Alarm|2015|62000|3000||In stock",
    "BMW|3 Series 320i luxury|2017|62000|5000||In stock",
    "Audi|A5 2.0TFSI Kuwatoro|2015|60000|5000||In stock",
    "Lexus|NX 200t I package spare T|2016|82000|10000||In stock",
    "Honda|Vezel e:HEV Z|2023|8000|16000|Hybrid|In stock",
    "Lexus|UX 250h version C|2019|16000|17000|Hybrid|In stock",
    "Lexus|RX RX450h version L|2019|54000|23000|Hybrid|In stock",
    "Toyota|Voxy ZS Sparkle|2015|83000|10000||In stock",
    "Lexus|Lbx Relax|2024|26000|27850|Hybrid|In stock",
    "Lexus|Lbx elegant|2025|7000|29300|Hybrid|In stock",
    "Mazda|MAZDA2 XD|2023|24000|10350|Diesel|In stock",
    "Lexus|RX RX450h F sports|2020|124000|20700|Hybrid|In stock",
    "Mazda|MAZDA2 XD|2019|65000|6650|Diesel|In stock",
    "Lexus|Lbx elegant|2025|10000|28950|Hybrid|In stock",
    "Lexus|Lbx relax|2024|16000|29300|Hybrid|In stock",
    "Lexus|Lbx relax|2024|18000|30000|Hybrid|In stock",
    "Nissan|AD Van VE|2021|28000|6450||In stock",
    "Honda|Vezel Z|2025|23000|20350|Hybrid|In stock",
    "Mazda|MAZDA2 15S|2019|18000|8700||In stock",
    "Lexus|UX 250h_F Sports|2021|52000|23500|Hybrid|In stock",
    "Lexus|Lbx cool|2024|11000|31050|Hybrid|In stock",
    "Honda|Vezel Z|2025|15000|20000|Hybrid|In stock",
    "Lexus|Lbx Morizou RR|2026|10000|40000||In stock",
    "Lexus|RX 450h-version L|2021|33000|35700|Hybrid|In stock",
    "Mazda|MAZDA2 15S|2019|43000|8450||In stock",
    "Mazda|MAZDA2 15S|2022|35000|10000||In stock",
    "Mazda|Axela 15S|2018|84000|7150||In stock",
    "Lexus|Lbx cool|2024|14000|30350|Hybrid|In stock",
    "Lexus|Lbx relax|2024|12000|30000|Hybrid|In stock",
    "Mazda|MAZDA2 15S|2020|51000|7700||In stock",
    "Mazda|MAZDA2 15S|2019|85000|6050||In stock",
    "Mazda|Axela 15S|2018|34000|9900||In stock",
    "Mazda|Atenza Wagon XD|2018|54000|12850|Diesel|In stock",
    "Nissan|AD Van VE|2021|55000|6150||In stock",
    "Lexus|Lbx relax|2024|19000|30000|Hybrid|In stock",
    "Lexus|RX 2.0 300|2021|30000|26350||In stock",
    "Lexus|RX F sport performance|2023|11000|50450|Hybrid|In stock",
    "Mazda|MAZDA2 15SL package|2020|38000|8950||In stock",
    "Mazda|Axela 15S|2018|44000|9850||In stock",
    "Lexus|IS IS300H|2025|6000|32800|Hybrid|In stock",
    "Mazda|CX 5 XD Sports Appearance|2022|66000|12400|Light Oil|In stock",
    "Honda|N Box L turbo|2022|39000|8500||In stock",
    "Toyota|Corolla Cross Z|2024|23000|14100||In stock",
    "Honda|Vezel e:HEV Z|2025|24000|16500|Hybrid|In stock",
    "Honda|N Box L|2022|6000|7200||In stock",
    "Toyota|RAV4 Adventurer|2023|24000|18200||In stock",
    "Mitsubishi|Delica Mini T|2024|11000|9500|Hybrid|In stock",
    "Mazda|CX 5 20S Proactive|2018|49000|9100||In stock",
    "Honda|Fit e:HEV home|2022|42000|7900|Hybrid|In stock",
    "Honda|N Box G L package|2015|91000|2800||In stock",
    "Nissan|Note S|2021|46000|5600|Hybrid|In stock",
    "Honda|Fit 13G F package|2014|60000|2300||In stock",
    "Nissan|Note X|2021|19000|9500|Hybrid|In stock",
    "Mazda|Demio 13S Touring|2018|49000|4400||In stock",
    "Mitsubishi|Delica D5 P|2024|17000|20500|Light Oil|In stock",
    "Nissan|Dayz Highway Star X|2020|2000|5000|Hybrid|In stock",
    "Toyota|RAV4 Hybrid G|2019|20000|15800|Hybrid|In stock",
    "Nissan|Note e-power X|2019|69000|4100|Hybrid|In stock",
    "Nissan|Note e-power X|2018|117000|2800|Hybrid|In stock",
    "Toyota|Aqua S style black|2019|102000|4300|Hybrid|In stock",
    "Honda|N Box G L Hondasensing|2019|34000|5600||In stock",
    "Lexus|RX RX200t version L|2015|158000|10900||In stock",
    "Toyota|Prado TX L package|2017|109000|17800|Light Oil|In stock",
    "Lexus|ES ES300h version L|2019|87000|13900||In stock",
    "Lexus|NX NX350h F sports|2023|56000|26700||In stock",
    "Lexus|CT CT200h version C|2016|62000|6800||In stock",
    "Lexus|NX NX300h urban style|2017|66000|14300||In stock",
    "Lexus|UX UX200 F sports|2018|33000|14300||In stock",
    "Honda|Vezel Hybrid e:HEV Z|2024|8000|16700||In stock",
    "Nissan|X Trail 20X hybrid emergen|2016|138000|4200||In stock",
    "Lexus|CT CT200h version C|2017|51000|9500||In stock",
    "Honda|Freed G Honda sensing|2017|108000|5600||In stock",
    "Lexus|RX RX500h|2024|50000|35700|Hybrid|In stock",
    "Lexus|NX NX350h F sports|2022|62000|24800|Hybrid|In stock",
    "Honda|Fit 13G|2014|42000|3200||In stock",
    "Toyota|Hiace Van Super GL Dark Prime II|2026|2000|23500||In stock",
    "Toyota|Hiace Van Super GL Dark Prime II|2021|42000|20200|Light Oil|In stock",
    "Honda|N Box SS package|2017|128000|1800||In stock",
    "Honda|Stepwgn e:HEV Spada G EX Honta|2021|119000|8800|Hybrid|In stock",
    "Nissan|Note Medalist|2016|39000|2700||In stock",
    "Toyota|Aqua G|2016|101000|2400|Hybrid|In stock",
    "Mazda|CX 3 XD Touring|2016|121000|3500|Light Oil|In stock",
    "Honda|N Box G L Hondasensing|2018|40000|5800||In stock",
    "Nissan|Dayz Roox Highway Star X|2019|29000|5300||In stock",
    "Honda|Stepwgn Spada|2024|54000|18800||In stock",
    "Honda|N Box Base grade|2025|13000|8700||In stock",
    "Toyota|Prado TX L package 70th Aniva|2022|26000|25000||In stock",
    "Honda|N Box G L Hondasensing|2017|61000|4400||In stock",
    "Mazda|CX 8 XD black tone edition|2021|55000|11600|Light Oil|In stock",
    "Mazda|CX 3 XD L package|2018|76000|5600|Light Oil|In stock",
    "Toyota|Aqua G G's|2016|80000|4800|Hybrid|In stock",
    "Mitsubishi|Delica D5 2.2 P diesel turbo 4W|2026||34700|Light Oil|In stock",
    "Mitsubishi|Delica D5 2.2 P diesel turbo 4W|2019|23000|22400|Light Oil|In stock",
    "Lexus|CT 200h version C|2017|58000|11500|Hybrid|In stock",
    "Toyota|Aqua X-urban|2015|135000|2700||In stock",
    "Honda|Vezel e:HEV|2026||20600||In stock",
    "Honda|N Box L turbo|2021|20000|7900||In stock",
    "Honda|Freed G|2024|18000|12600||In stock",
    "Toyota|RAV4 adventure|2023|32000|25000|Hybrid|In stock",
    "Toyota|RAV4 G|2020|58000|14400|Hybrid|In stock",
    "Toyota|RAV4 adventure|2019|74000|16450||In stock",
    "Toyota|RAV4 G|2023|21000|24650|Hybrid|In stock",
    "Toyota|RAV4 adventure|2024|37000|25650|Hybrid|In stock",
    "Subaru|Impreza Wagon 1.6i-L Eyesight S|2018|79000|6050||In stock",
    "Subaru|Impreza Wagon 1.6i-S Eyesight|2020|50000|9300||In stock",
    "Toyota|86 RZ|2024|34000|23650||In stock",
    "Toyota|86 GT Limited|2019|32000|14800||In stock",
    "Subaru|XV 2.0i-L Eyesight|2019|58000|9650||In stock",
    "Toyota|RAV4 adventure|2024|31000|25000|Hybrid|In stock",
    "Subaru|Impreza Wagon 2.0i-L Eyesight|2018|62000|5850||In stock",
    "Subaru|XV advance|2021|52000|13300|Hybrid|In stock",
    "Toyota|RAV4 G|2023|19000|25350|Hybrid|In stock",
    "Toyota|RAV4 adventure|2021|44000|17500||In stock",
    "Subaru|XV 2.0i-L Eyesight|2018|20000|12150||In stock",
    "Toyota|86 RZ|2022|18000|25350||In stock",
]


def seed_car_rows():
    """Parse the compact SAMPLE_CARS strings into database rows."""
    rows = []
    for line in SAMPLE_CARS:
        make, model, year, km, price, body, status = line.split("|")
        rows.append((make, model, int(year),
                     int(km) if km else None, int(price), body, status))
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
     "We have over 1,000 cars in our regular stock, and about 100,000 "
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
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY, question TEXT, answer TEXT,
            topic TEXT);
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
    # Add sample cars only the first time, when the table is empty.
    count = db.execute("SELECT COUNT(*) FROM cars").fetchone()[0]
    if count == 0:
        db.executemany(
            "INSERT INTO cars (make, model, year, distance_km, price_fob,"
            " body_type, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
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
    return render_template(
        "admin.html", health={"app": "Running", "db_ok": db_ok,
                              "tables": tables,
                              "cache_hits": _CACHE_STATS["hits"],
                              "cache_misses": _CACHE_STATS["misses"],
                              "cached_tables": sorted(_CACHE.keys())},
        counts=counts, users=users, chats=chats, messages=messages,
        questions=questions, faqs=faqs, cars=cars, invoices=invoices,
        ships=ships)


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
    """Tiny health page: is the bot up, and is the cache working?"""
    return jsonify({
        "status": "ok",
        "cache_hits": _CACHE_STATS["hits"],
        "cache_misses": _CACHE_STATS["misses"],
        "cached_tables": sorted(_CACHE.keys()),
    })


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


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Chat API. JavaScript sends a message, the bot answers as JSON."""
    data = request.get_json(force=True)
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"reply": "Please type a question first."})
    # Guests can still chat, but guest chats are NOT saved.
    # Only signed-in users get their chat history saved.
    user = current_user()
    if user is None:
        return jsonify({"reply": bot_reply(text, None, None)})
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
    return jsonify({"reply": reply, "chat_id": chat["id"]})


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
