"""
seed_data.py — Seeds historical_shipments with 250 realistic records
across major world ports to power the Historical Agent (Module 4).

Usage: python seed_data.py
Idempotent — clears existing records and re-seeds cleanly.
"""
import random
import sys
import os
from datetime import date, timedelta

# Ensure we can import from the app
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import mysql.connector

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASS = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB   = os.getenv("MYSQL_DATABASE", "shipment_risk_db")

PORTS = [
    # (port_name, base_delay_rate, seasonal_peak_months)
    ("Jebel Ali",         0.22, [6, 7, 8, 12]),
    ("Singapore",         0.14, [11, 12, 1]),
    ("Shanghai",          0.28, [1, 2, 10, 11]),
    ("Rotterdam",         0.19, [12, 1, 2]),
    ("Hamburg",           0.20, [12, 1, 2]),
    ("Los Angeles",       0.31, [10, 11, 12]),
    ("Colombo",           0.25, [6, 7, 8]),
    ("Nhava Sheva",       0.35, [6, 7, 8, 9]),
    ("Durban",            0.28, [11, 12, 1]),
    ("Antwerp",           0.17, [12, 1]),
    ("Busan",             0.16, [1, 2, 7, 8]),
    ("Port Klang",        0.21, [7, 8, 9]),
    ("Piraeus",           0.24, [7, 8]),
    ("Felixstowe",        0.22, [11, 12]),
    ("Hamad Port",        0.18, [6, 7, 8]),
    ("Hong Kong",         0.15, [9, 10, 11]),
    ("Santos",            0.30, [1, 2, 12]),
    ("Mombasa",           0.38, [4, 5, 6]),
    ("Long Beach",        0.29, [10, 11, 12]),
    ("Tanger Med",        0.20, [7, 8]),
]

CARGO_TYPES = ["electronics", "perishables", "automotive", "chemicals", "textiles",
               "machinery", "general", "general", "general"]  # general weighted

DELAY_REASONS = {
    "weather":        ["Storm conditions at port", "High winds — berth closure", "Fog — reduced visibility"],
    "congestion":     ["Terminal congestion", "Berth unavailability", "High vessel queue"],
    "documentation":  ["Customs hold", "Documentation error", "Inspection delay"],
    "labour":         ["Port worker strike", "Labour dispute — partial operations"],
    "technical":      ["Crane breakdown", "Equipment malfunction at terminal"],
    "geopolitical":   ["Sanctions-related delay", "Border control delays"],
    "none":           [None],
}

SEASONS = {1:"winter",2:"winter",3:"spring",4:"spring",5:"spring",
           6:"summer",7:"summer",8:"summer",9:"autumn",10:"autumn",
           11:"autumn",12:"winter"}

def seed():
    conn = mysql.connector.connect(
        host=MYSQL_HOST, user=MYSQL_USER,
        password=MYSQL_PASS, database=MYSQL_DB, charset="utf8mb4"
    )
    cursor = conn.cursor()

    # Clear existing
    cursor.execute("DELETE FROM historical_shipments")
    conn.commit()
    print(f"Cleared existing historical records.")

    records = []
    today = date.today()

    for port_name, base_rate, peak_months in PORTS:
        n_records = random.randint(10, 16)

        for _ in range(n_records):
            # Random date in past 2 years
            days_back = random.randint(10, 730)
            sched_date = today - timedelta(days=days_back)
            month = sched_date.month

            # Seasonal adjustment
            if month in peak_months:
                delay_rate = min(base_rate * random.uniform(1.4, 2.0), 0.75)
            else:
                delay_rate = base_rate * random.uniform(0.6, 1.2)

            is_delayed = random.random() < delay_rate

            if is_delayed:
                delay_days = random.choices(
                    [1, 2, 3, 4, 5, 7, 10, 14],
                    weights=[20, 22, 18, 12, 10, 8, 6, 4]
                )[0]
                reason_cat = random.choices(
                    list(DELAY_REASONS.keys()),
                    weights=[15, 35, 20, 10, 10, 5, 5]
                )[0]
                reason = random.choice(DELAY_REASONS[reason_cat])
                actual_date = sched_date + timedelta(days=delay_days)
            else:
                delay_days  = random.choice([0, 0, 0, -1, -1, -2])  # sometimes early
                reason      = None
                actual_date = sched_date + timedelta(days=delay_days)

            cargo = random.choice(CARGO_TYPES)
            origin_ports = [p[0] for p in PORTS if p[0] != port_name]
            origin = random.choice(origin_ports)

            records.append((
                port_name, origin, cargo,
                sched_date, actual_date, delay_days, reason,
                SEASONS[month], sched_date.year, month,
            ))

    cursor.executemany(
        """INSERT INTO historical_shipments
           (port, origin_port, cargo_type, scheduled_date, actual_date,
            delay_days, delay_reason, season, year, month)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        records,
    )
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM historical_shipments")
    count = cursor.fetchone()[0]
    print(f"[OK] Seeded {count} historical shipment records across {len(PORTS)} ports.")

    # Show breakdown
    cursor.execute("""
        SELECT port, COUNT(*) as total,
               SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) as num_delayed
        FROM historical_shipments
        GROUP BY port ORDER BY total DESC
    """)
    print(f"\n{'Port':<25} {'Total':>6} {'Delayed':>8} {'Rate':>7}")
    print("-" * 50)
    for row in cursor.fetchall():
        port_name = row[0]
        total     = row[1] or 0
        num_del   = row[2] or 0
        rate      = num_del / total * 100 if total else 0
        print(f"{port_name:<25} {total:>6} {num_del:>8} {rate:>6.0f}%")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    seed()
