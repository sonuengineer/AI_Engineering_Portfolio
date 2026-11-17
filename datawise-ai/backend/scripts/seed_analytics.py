"""Create and seed the synthetic analytics database (datawise_analytics).

Deterministic: a fixed random seed means every run produces identical data, so the evaluation
dataset's expected values (evaluation/build_expected.py) stay valid.

Data window: 2024-11-01 .. 2026-10-31 (24 months).

Usage (from backend/):
    uv run python -m scripts.seed_analytics            # seed only if tables are empty
    uv run python -m scripts.seed_analytics --reset    # drop + recreate + seed
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta

import psycopg

from app.core.config import get_settings

SEED = 20241101
START = date(2024, 11, 1)
END = date(2026, 10, 31)

N_CUSTOMERS = 500
N_SUPPLIERS = 25
N_ORDERS = 8000
N_SESSIONS = 40000
N_DELIVERIES = 1500

REGIONS = ["North", "South", "East", "West", "Central"]
SEGMENTS = [("Consumer", 0.6), ("Small Business", 0.3), ("Enterprise", 0.1)]
CHANNELS = [("web", 0.55), ("mobile", 0.3), ("store", 0.15)]
STATUSES = [("completed", 0.84), ("shipped", 0.06), ("cancelled", 0.07), ("returned", 0.03)]
TRAFFIC_SOURCES = [("organic", 0.35), ("paid_search", 0.25), ("email", 0.15), ("social", 0.15), ("direct", 0.10)]
DEVICES = [("desktop", 0.5), ("mobile", 0.42), ("tablet", 0.08)]

# category -> (price range, base names)
CATEGORIES: dict[str, tuple[tuple[float, float], list[str]]] = {
    "Electronics": ((40, 900), ["Wireless Earbuds", "4K Monitor", "Laptop Stand", "USB-C Hub", "Smart Speaker",
                                "Mechanical Keyboard", "Webcam", "Portable SSD", "Noise-Cancel Headphones",
                                "Bluetooth Mouse", "Tablet", "Smartwatch", "Power Bank", "HDMI Switch", "Router"]),
    "Home & Kitchen": ((15, 300), ["Espresso Maker", "Air Fryer", "Chef Knife", "Cast Iron Pan", "Blender",
                                   "Electric Kettle", "Cutting Board", "Food Storage Set", "Toaster",
                                   "Stand Mixer", "Rice Cooker", "Water Filter", "Dish Rack", "Cookware Set",
                                   "Coffee Grinder"]),
    "Office Supplies": ((3, 120), ["Gel Pens", "Notebook", "Desk Organizer", "Stapler", "Sticky Notes",
                                   "Paper Ream", "Whiteboard", "Label Maker", "File Folders", "Desk Lamp",
                                   "Ergonomic Chair Cushion", "Monitor Riser", "Highlighters", "Binder Clips",
                                   "Planner"]),
    "Sports & Outdoors": ((10, 400), ["Yoga Mat", "Dumbbell Set", "Camping Tent", "Hiking Backpack",
                                      "Water Bottle", "Running Shoes", "Bike Helmet", "Resistance Bands",
                                      "Sleeping Bag", "Trekking Poles", "Jump Rope", "Foam Roller",
                                      "Cooler Box", "Headlamp", "Fitness Tracker"]),
    "Toys & Games": ((8, 150), ["Building Blocks", "Board Game", "Puzzle 1000pc", "RC Car", "Plush Bear",
                                "Card Game", "Science Kit", "Art Set", "Doll House", "Train Set",
                                "Drone Mini", "Magnetic Tiles", "Kite", "Water Blaster", "Chess Set"]),
    "Beauty": ((5, 90), ["Face Serum", "Moisturizer", "Shampoo", "Conditioner", "Sunscreen", "Lip Balm",
                         "Hair Dryer", "Body Lotion", "Face Mask", "Nail Kit", "Perfume", "Beard Oil",
                         "Makeup Brush Set", "Hand Cream", "Cleanser"]),
    "Grocery": ((2, 40), ["Olive Oil", "Ground Coffee", "Green Tea", "Dark Chocolate", "Granola", "Pasta",
                          "Honey", "Almonds", "Protein Bars", "Sparkling Water", "Oat Milk", "Spice Kit",
                          "Maple Syrup", "Peanut Butter", "Rice 5kg"]),
    "Apparel": ((12, 180), ["Rain Jacket", "Wool Sweater", "Denim Jeans", "T-Shirt Pack", "Sneakers",
                            "Fleece Hoodie", "Winter Gloves", "Baseball Cap", "Socks 6-Pack", "Chino Pants",
                            "Running Shorts", "Scarf", "Leather Belt", "Polo Shirt", "Down Vest"]),
}
PRODUCTS_PER_CATEGORY = 15  # 8 categories * 15 = 120 products

SUPPLIER_WORDS_A = ["Northwind", "Bluepeak", "Summit", "Harbor", "Ironwood", "Silverline", "Redrock", "Greenfield",
                    "Brightway", "Oakridge", "Clearwater", "Stonebridge", "Goldleaf", "Pinecrest", "Riverbend",
                    "Sunvale", "Maplewood", "Eastgate", "Westport", "Highland", "Lakeside", "Cedar", "Falcon",
                    "Atlas", "Crescent"]
SUPPLIER_SUFFIX = ["Trading", "Supply Co", "Distribution", "Manufacturing", "Imports", "Wholesale", "Logistics"]
SUPPLIER_COUNTRIES = ["USA", "Mexico", "Canada", "China", "Vietnam", "Germany", "India"]

FIRST = ["Ava", "Liam", "Noah", "Emma", "Olivia", "Mia", "Lucas", "Ethan", "Sofia", "Amir", "Priya", "Chen",
         "Diego", "Fatima", "Hana", "Ivan", "Jade", "Kofi", "Lena", "Mateo", "Nina", "Omar", "Quinn", "Ravi",
         "Sara", "Tomas", "Uma", "Victor", "Wen", "Yara", "Zane", "Grace", "Henry", "Isla", "Jonas", "Kira"]
LAST = ["Smith", "Garcia", "Chen", "Patel", "Kim", "Nguyen", "Johnson", "Lopez", "Brown", "Singh", "Muller",
        "Rossi", "Silva", "Khan", "Martin", "Okafor", "Novak", "Larsen", "Tanaka", "Haddad", "Cohen", "Ward",
        "Reyes", "Price", "Fischer", "Moreau", "Ibrahim", "Costa", "Walsh", "Park"]
BIZ_A = ["Apex", "Vertex", "Nimbus", "Quantum", "Pioneer", "Beacon", "Keystone", "Horizon", "Evergreen", "Sterling",
         "Momentum", "Cobalt", "Granite", "Lumen", "Orbit", "Prairie", "Radiant", "Sequoia", "Tidal", "Vanguard"]
BIZ_B = ["Labs", "Partners", "Holdings", "Studio", "Group", "Systems", "Works", "Ventures", "Foods", "Health",
         "Retail", "Dynamics", "Consulting", "Media", "Logistics"]
CITIES = {"North": ["Minneapolis", "Fargo", "Duluth"], "South": ["Austin", "Atlanta", "Miami"],
          "East": ["Boston", "New York", "Philadelphia"], "West": ["Seattle", "San Diego", "Portland"],
          "Central": ["Chicago", "Denver", "Kansas City"]}

DDL = """
DROP TABLE IF EXISTS order_items, orders, supplier_deliveries, web_sessions, products, customers, suppliers CASCADE;

CREATE TABLE suppliers (
    supplier_id   INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    country       TEXT NOT NULL
);
CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    category      TEXT NOT NULL,
    supplier_id   INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    unit_cost     NUMERIC(10,2) NOT NULL,
    list_price    NUMERIC(10,2) NOT NULL
);
CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    segment       TEXT NOT NULL,
    region        TEXT NOT NULL,
    city          TEXT NOT NULL,
    signup_date   DATE NOT NULL
);
CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date    DATE NOT NULL,
    status        TEXT NOT NULL,
    channel       TEXT NOT NULL
);
CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10,2) NOT NULL
);
CREATE TABLE web_sessions (
    session_id     INTEGER PRIMARY KEY,
    session_date   DATE NOT NULL,
    region         TEXT NOT NULL,
    traffic_source TEXT NOT NULL,
    device         TEXT NOT NULL,
    viewed_product BOOLEAN NOT NULL,
    added_to_cart  BOOLEAN NOT NULL,
    converted      BOOLEAN NOT NULL
);
CREATE TABLE supplier_deliveries (
    delivery_id    INTEGER PRIMARY KEY,
    supplier_id    INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    product_id     INTEGER NOT NULL REFERENCES products(product_id),
    ordered_date   DATE NOT NULL,
    promised_date  DATE NOT NULL,
    delivered_date DATE NOT NULL,
    quantity       INTEGER NOT NULL,
    lead_time_days INTEGER NOT NULL,
    on_time        BOOLEAN NOT NULL
);
CREATE INDEX ix_orders_date ON orders(order_date);
CREATE INDEX ix_orders_customer ON orders(customer_id);
CREATE INDEX ix_order_items_order ON order_items(order_id);
CREATE INDEX ix_order_items_product ON order_items(product_id);
CREATE INDEX ix_sessions_date ON web_sessions(session_date);
CREATE INDEX ix_deliveries_date ON supplier_deliveries(delivered_date);
"""

GRANTS = """
GRANT USAGE ON SCHEMA public TO datawise_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO datawise_reader;
"""


def _pick(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
    return rng.choices([w[0] for w in weighted], weights=[w[1] for w in weighted], k=1)[0]


def _days() -> list[date]:
    out: list[date] = []
    d = START
    while d <= END:
        out.append(d)
        d += timedelta(days=1)
    return out


def _day_weight(d: date) -> float:
    """Seasonality (Nov/Dec peak, summer dip) + ~25% yearly growth trend + weekend lift."""
    month_factor = {1: 0.8, 2: 0.8, 3: 0.95, 4: 1.0, 5: 1.0, 6: 0.9, 7: 0.85, 8: 0.9, 9: 1.0, 10: 1.05,
                    11: 1.35, 12: 1.6}[d.month]
    trend = 1.0 + 0.25 * ((d - START).days / 365.0)
    weekend = 1.15 if d.weekday() >= 5 else 1.0
    return month_factor * trend * weekend


def generate(rng: random.Random) -> dict[str, list[tuple[object, ...]]]:
    # suppliers
    supplier_names: list[str] = []
    for i, word in enumerate(SUPPLIER_WORDS_A[:N_SUPPLIERS]):
        supplier_names.append(f"{word} {SUPPLIER_SUFFIX[i % len(SUPPLIER_SUFFIX)]}")
    suppliers: list[tuple[object, ...]] = [
        (i + 1, n, rng.choice(SUPPLIER_COUNTRIES)) for i, n in enumerate(supplier_names)
    ]
    supplier_reliability = {s[0]: rng.uniform(0.70, 0.97) for s in suppliers}
    supplier_lead = {s[0]: rng.randint(5, 28) for s in suppliers}

    # products
    products: list[tuple[object, ...]] = []
    pid = 0
    for cat, ((lo, hi), names) in CATEGORIES.items():
        for name in names[:PRODUCTS_PER_CATEGORY]:
            pid += 1
            price = round(rng.uniform(lo, hi), 2)
            cost = round(price * rng.uniform(0.45, 0.75), 2)
            products.append((pid, name, cat, rng.randint(1, N_SUPPLIERS), cost, price))
    product_popularity = [rng.paretovariate(1.6) for _ in products]

    # customers
    customers: list[tuple[object, ...]] = []
    used: set[str] = set()
    for cid in range(1, N_CUSTOMERS + 1):
        segment = _pick(rng, SEGMENTS)
        while True:
            if segment == "Consumer":
                name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            else:
                name = f"{rng.choice(BIZ_A)} {rng.choice(BIZ_B)}"
            if name not in used:
                used.add(name)
                break
        region = rng.choices(REGIONS, weights=[0.18, 0.24, 0.22, 0.24, 0.12], k=1)[0]
        signup = START - timedelta(days=rng.randint(0, 900))
        customers.append((cid, name, segment, region, rng.choice(CITIES[region]), signup))
    customer_activity = [
        rng.paretovariate(1.3) * {"Consumer": 1.0, "Small Business": 1.6, "Enterprise": 2.6}[str(c[2])]
        for c in customers
    ]
    seg_qty = {"Consumer": (1, 3), "Small Business": (1, 6), "Enterprise": (2, 12)}

    # orders + items
    days = _days()
    day_weights = [_day_weight(d) for d in days]
    order_days = sorted(rng.choices(days, weights=day_weights, k=N_ORDERS))
    orders: list[tuple[object, ...]] = []
    items: list[tuple[object, ...]] = []
    item_id = 0
    for oid, od in enumerate(order_days, start=1):
        cust = rng.choices(customers, weights=customer_activity, k=1)[0]
        status = _pick(rng, STATUSES)
        # recent orders are more likely to still be "shipped"
        if (END - od).days < 10 and status == "completed":
            status = "shipped"
        orders.append((oid, cust[0], od, status, _pick(rng, CHANNELS)))
        n_items = rng.choices([1, 2, 3, 4, 5], weights=[0.35, 0.3, 0.18, 0.1, 0.07], k=1)[0]
        chosen = set()
        for _ in range(n_items):
            prod = rng.choices(products, weights=product_popularity, k=1)[0]
            if prod[0] in chosen:
                continue
            chosen.add(prod[0])
            item_id += 1
            lo, hi = seg_qty[str(cust[2])]
            qty = rng.randint(lo, hi)
            discount = rng.choice([1.0, 1.0, 1.0, 0.95, 0.9, 0.85])
            unit_price = round(float(prod[5]) * discount, 2)  # type: ignore[arg-type]
            items.append((item_id, oid, prod[0], qty, unit_price))

    # web sessions (conversion funnel)
    sessions: list[tuple[object, ...]] = []
    session_days = sorted(rng.choices(days, weights=day_weights, k=N_SESSIONS))
    src_conv = {"organic": 1.0, "paid_search": 1.15, "email": 1.5, "social": 0.6, "direct": 1.25}
    dev_conv = {"desktop": 1.2, "mobile": 0.8, "tablet": 0.9}
    for sid, sd in enumerate(session_days, start=1):
        src = _pick(rng, TRAFFIC_SOURCES)
        dev = _pick(rng, DEVICES)
        region = rng.choices(REGIONS, weights=[0.18, 0.24, 0.22, 0.24, 0.12], k=1)[0]
        viewed = rng.random() < 0.62
        cart = viewed and rng.random() < 0.28 * src_conv[src]
        season = 1.25 if sd.month in (11, 12) else 1.0
        converted = cart and rng.random() < min(0.95, 0.42 * dev_conv[dev] * season)
        sessions.append((sid, sd, region, src, dev, viewed, cart, converted))

    # supplier deliveries
    deliveries: list[tuple[object, ...]] = []
    for did in range(1, N_DELIVERIES + 1):
        prod = rng.choice(products)
        sup_id = int(prod[3])  # type: ignore[call-overload]
        ordered = START + timedelta(days=rng.randint(0, (END - START).days - 45))
        promised_lead = supplier_lead[sup_id]
        promised = ordered + timedelta(days=promised_lead)
        if rng.random() < supplier_reliability[sup_id]:
            actual_lead = promised_lead - rng.randint(0, 3)
        else:
            actual_lead = promised_lead + rng.randint(1, 12)
        actual_lead = max(1, actual_lead)
        delivered = ordered + timedelta(days=actual_lead)
        if delivered > END:
            delivered = END
            actual_lead = (delivered - ordered).days
        deliveries.append((did, sup_id, prod[0], ordered, promised, delivered, rng.randint(20, 500),
                           actual_lead, delivered <= promised))

    return {
        "suppliers": suppliers,
        "products": products,
        "customers": customers,
        "orders": orders,
        "order_items": items,
        "web_sessions": sessions,
        "supplier_deliveries": deliveries,
    }


def _copy(cur: psycopg.Cursor, table: str, rows: list[tuple[object, ...]]) -> None:
    with cur.copy(f"COPY {table} FROM STDIN") as cp:
        for r in rows:
            cp.write_row(r)


def seed(reset: bool) -> None:
    url = get_settings().analytics_admin_database_url
    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.orders') IS NOT NULL")
        row = cur.fetchone()
        exists = bool(row and row[0])
        if exists and not reset:
            cur.execute("SELECT count(*) FROM orders")
            n = cur.fetchone()
            if n and n[0] > 0:
                print(f"analytics already seeded ({n[0]} orders); use --reset to rebuild")
                cur.execute(GRANTS)
                conn.commit()
                return
        data = generate(random.Random(SEED))
        cur.execute(DDL)
        for table in ["suppliers", "products", "customers", "orders", "order_items", "web_sessions",
                      "supplier_deliveries"]:
            _copy(cur, table, data[table])
        cur.execute(GRANTS)
        cur.execute("ANALYZE")
        conn.commit()
        counts = {k: len(v) for k, v in data.items()}
        print("seeded analytics:", counts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reset", action="store_true", help="drop and rebuild all analytics tables")
    args = p.parse_args(argv)
    seed(reset=args.reset)
    return 0


if __name__ == "__main__":
    sys.exit(main())

