"""Reproducible synthetic seed data for NEXUS AI.

Usage:  python -m scripts.seed [--reset]

Fixed random seed + fixed AS_OF date => identical data on every run (needed for EvalOps benchmarks).
Documents go through the real ingestion pipeline (validation -> extraction -> chunking -> embedding).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import Base, session_factory
from app.core.security import hash_password
from app.ingestion.indexer import EXT_BY_MIME
from app.ingestion.jobs import drain, enqueue
from app.ingestion.storage import ObjectStorage, get_storage
from app.ingestion.validation import validate_upload
from app.models import (
    CrmCustomer,
    Document,
    EmailRecord,
    ErpOrder,
    ErpQuotation,
    Organization,
    User,
)
from app.seed_data import binary_docs as bd

SEED = 20261116
AS_OF = date(2026, 10, 31)
SEED_DIR = Path(__file__).resolve().parents[1] / "app" / "seed_data"

# name, industry, region, tier, monthly_base_revenue, recent_factor, scenario
CUSTOMERS = [
    ("Northwind Fabrication", "Metal Fabrication", "Midwest", "Platinum", 185_000, 0.62, "pricing"),
    ("Bluepeak Energy", "Energy", "Southwest", "Platinum", 172_000, 0.58, "delivery"),
    ("Harbor Marine Systems", "Marine", "Northeast", "Gold", 151_000, 0.55, "quality"),
    ("Summit Foods Processing", "Food Processing", "Mountain", "Gold", 139_000, 0.66, "budget"),
    ("Ironclad Construction", "Construction", "Southeast", "Gold", 128_000, 0.70, "contract"),
    ("Cedar Valley Utilities", "Utilities", "Pacific", "Gold", 117_000, 0.80, "none"),
    ("Granite Peak Mining", "Mining", "Mountain", "Gold", 160_000, 1.04, "stable"),
    ("Riverside Medical Devices", "Medical", "Northeast", "Platinum", 145_000, 1.12, "growing"),
    ("Atlas Logistics Group", "Logistics", "Midwest", "Gold", 122_000, 0.97, "stable"),
    ("Pioneer Agritech", "Agriculture", "Midwest", "Gold", 110_000, 1.08, "growing"),
]
FILLER_NAMES = [
    "Orion Plastics",
    "Maple Ridge Packaging",
    "Silverline Rail",
    "Falcon Aerospace Parts",
    "Evergreen Paper Mill",
    "Coastal Water Works",
    "Redwood Furniture Co",
    "Vector Robotics",
    "Keystone Chemicals",
    "Lakeshore Brewing",
    "Prairie Wind Farms",
    "Copperhead Electric",
    "Blue Harbor Seafood",
    "Meridian Textiles",
    "Stonebridge Builders",
    "Polar Cold Storage",
    "Sunrise Bakeries",
    "Trident Shipyards",
    "Highland Dairy",
    "Quantum Semiconductors",
    "Bayview Hospitals",
    "Ridgeway Auto Parts",
    "Westfield Glassworks",
    "Canyon Cement",
    "Northstar Printing",
    "Ivory Ceramics",
    "Juniper Pharmaceuticals",
    "Crescent Hotels",
    "Delta Irrigation",
    "Summit Ski Resorts",
]
PRODUCT_LINES = ["Fasteners", "Conveyor Parts", "Hydraulics", "Safety Equipment", "Electrical", "Marine Coatings"]
SCENARIO_LINE = {
    "pricing": "Fasteners",
    "delivery": "Hydraulics",
    "quality": "Marine Coatings",
    "budget": "Conveyor Parts",
    "contract": "Safety Equipment",
    "none": "Electrical",
}
MANAGERS = ["Priya Raman", "Marcus Lee", "Elena Petrova", "Samuel Okafor"]


def _month_starts(n: int) -> list[date]:
    out, y, m = [], AS_OF.year, AS_OF.month
    for _ in range(n):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def reset(db: Session) -> None:
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    db.execute(text(f"TRUNCATE {tables} CASCADE"))
    db.commit()


def _users(db: Session, org: Organization, domain: str, pw_hash: str, roles: list[tuple[str, str]]) -> None:
    for role, name in roles:
        db.add(User(org_id=org.id, email=f"{role}@{domain}", full_name=name, role=role, password_hash=pw_hash))


def seed(db: Session, storage: ObjectStorage, *, password: str | None = None) -> dict[str, int]:
    if db.scalar(select(Organization).where(Organization.slug == "acme")):
        return {"skipped": 1}
    rng = random.Random(SEED)
    pw_hash = hash_password(password or get_settings().demo_user_password)

    acme = Organization(name="Acme Industrial Supply", slug="acme")
    globex = Organization(name="Globex Distribution", slug="globex")
    db.add_all([acme, globex])
    db.flush()
    _users(
        db,
        acme,
        "acme.example",
        pw_hash,
        [
            ("admin", "Avery Admin"),
            ("manager", "Morgan Manager"),
            ("analyst", "Alex Analyst"),
            ("viewer", "Val Viewer"),
        ],
    )
    _users(db, globex, "globex.example", pw_hash, [("admin", "Gale Globex"), ("manager", "Glen Globex")])

    customers: list[tuple[CrmCustomer, float, float, str]] = []
    for i, (name, industry, region, tier, base, factor, scen) in enumerate(CUSTOMERS):
        customers.append((_customer(acme.id, i, name, industry, region, tier, rng), base, factor, scen))
    for j, name in enumerate(FILLER_NAMES):
        c = _customer(
            acme.id,
            len(CUSTOMERS) + j,
            name,
            rng.choice(["Manufacturing", "Retail", "Services", "Healthcare"]),
            rng.choice(["Midwest", "Northeast", "Pacific", "Southeast"]),
            rng.choice(["Silver", "Bronze"]),
            rng,
        )
        customers.append((c, rng.uniform(8_000, 45_000), rng.uniform(0.85, 1.15), "filler"))
    db.add_all([c for c, *_ in customers])
    db.flush()

    months = _month_starts(24)
    n_orders = 0
    for c, base, factor, scen in customers:
        for mi, mstart in enumerate(months):
            recent = mi >= 18  # last 6 months
            month_rev = base * (factor if recent else 1.0) * rng.uniform(0.9, 1.1)
            k = rng.randint(2, 4)
            for o in range(k):
                day = min(28, 1 + o * 7 + rng.randint(0, 5))
                line = (
                    SCENARIO_LINE.get(scen, rng.choice(PRODUCT_LINES))
                    if rng.random() < 0.6
                    else rng.choice(PRODUCT_LINES)
                )
                delay = rng.choice([0, 0, 0, 1, 2])
                if scen == "delivery" and recent:
                    delay = rng.randint(4, 10)
                status = "cancelled" if rng.random() < 0.03 else "completed"
                n_orders += 1
                db.add(
                    ErpOrder(
                        org_id=acme.id,
                        customer_id=c.id,
                        order_number=f"SO-{n_orders:06d}",
                        order_date=mstart.replace(day=day),
                        product_line=line,
                        quantity=rng.randint(10, 400),
                        amount=Decimal(f"{month_rev / k:.2f}"),
                        status=status,
                        delivery_delay_days=delay,
                    )
                )

    by_scen = {scen: c for c, _b, _f, scen in customers if scen not in ("filler",)}
    _quotes(db, acme.id, by_scen, [c for c, *_ in customers], rng)
    n_emails = _emails(db, acme.id, by_scen, [c for c, *_ in customers], rng)

    # Globex tenant gets a tiny dataset (tenant-isolation tests/demo).
    gx = _customer(globex.id, 0, "Globex Secret Customer", "Retail", "Pacific", "Gold", rng)
    db.add(gx)
    db.flush()
    db.add(
        ErpOrder(
            org_id=globex.id,
            customer_id=gx.id,
            order_number="GX-000001",
            order_date=AS_OF,
            product_line="Electrical",
            quantity=5,
            amount=Decimal("999.00"),
            status="completed",
        )
    )
    db.commit()

    n_docs = _documents(db, acme, globex, storage)
    drain(db, storage)
    return {"customers": len(customers) + 1, "orders": n_orders + 1, "emails": n_emails, "documents": n_docs}


def _customer(org_id: str, i: int, name: str, industry: str, region: str, tier: str, rng: random.Random) -> CrmCustomer:
    first = rng.choice(["Dana", "Lee", "Jordan", "Sam", "Riley", "Casey", "Taylor", "Morgan", "Jamie", "Avery"])
    last = rng.choice(["Ortiz", "Chen", "Patel", "Novak", "Haddad", "Kim", "Silva", "Brooks", "Ito", "Meyer"])
    if name == "Northwind Fabrication":
        first, last = "Dana", "Ortiz"
    slug = "".join(ch for ch in name.lower() if ch.isalnum())[:20]
    return CrmCustomer(
        org_id=org_id,
        code=f"C{1000 + i}",
        name=name,
        industry=industry,
        region=region,
        account_manager=MANAGERS[i % len(MANAGERS)],
        contact_name=f"{first} {last}",
        contact_email=f"{first.lower()}.{last.lower()}@{slug}.example",
        tier=tier,
    )


def _quotes(
    db: Session, org_id: str, by_scen: dict[str, CrmCustomer], all_c: list[CrmCustomer], rng: random.Random
) -> None:
    db.add(
        ErpQuotation(
            org_id=org_id,
            customer_id=by_scen["pricing"].id,
            quote_number="Q-2026-0412",
            issued_on=date(2026, 8, 19),
            valid_until=date(2026, 11, 30),
            amount=Decimal("486000.00"),
            status="pending",
            product_line="Fasteners",
        )
    )
    db.add(
        ErpQuotation(
            org_id=org_id,
            customer_id=by_scen["contract"].id,
            quote_number="Q-2026-0398",
            issued_on=date(2026, 7, 2),
            valid_until=date(2026, 12, 31),
            amount=Decimal("392500.00"),
            status="pending",
            product_line="Safety Equipment",
        )
    )
    for n, c in enumerate(all_c[:20]):
        db.add(
            ErpQuotation(
                org_id=org_id,
                customer_id=c.id,
                quote_number=f"Q-2026-{100 + n:04d}",
                issued_on=date(2026, rng.randint(1, 6), rng.randint(1, 28)),
                valid_until=date(2026, 9, 30),
                amount=Decimal(f"{rng.uniform(5000, 90000):.2f}"),
                status=rng.choice(["accepted", "accepted", "rejected", "expired"]),
                product_line=rng.choice(PRODUCT_LINES),
            )
        )


EMAILS = {
    "pricing": [
        (
            "inbound",
            "2026-06-03",
            "Fastener pricing review",
            "Hi Priya, we received a competitor offer from Steelway Metals that is about 8% cheaper on sheet-metal fasteners. We will trial them for part of our volume while we review pricing.",
        ),
        (
            "inbound",
            "2026-09-12",
            "RE: Q-2026-0412",
            "We are still reviewing quotation Q-2026-0412. Could you consider volume-based pricing tiers? Pricing remains our main concern.",
        ),
    ],
    "delivery": [
        (
            "inbound",
            "2026-06-21",
            "Late hydraulic deliveries",
            "Our last three hydraulic hose deliveries arrived late, one by 9 days. This delayed maintenance at two of our sites. We need reliable delivery dates.",
        ),
        (
            "inbound",
            "2026-08-30",
            "Delivery delays again",
            "Delivery delays are continuing after your warehouse relocation. We have started ordering urgent items from a local distributor.",
        ),
    ],
    "quality": [
        (
            "inbound",
            "2026-05-13",
            "Rejected batch MC-5521",
            "Batch MC-5521 failed adhesion tests on two vessels. We are rejecting the batch and filing a quality complaint.",
        ),
        (
            "inbound",
            "2026-07-08",
            "Dual sourcing marine coatings",
            "Until two consecutive batches pass inspection we will dual-source marine coatings. Please send the root cause report.",
        ),
    ],
    "budget": [
        (
            "inbound",
            "2026-07-15",
            "Budget freeze H2 2026",
            "Our parent company announced a budget freeze for the second half of 2026. Non-critical spare-part orders are deferred until January.",
        )
    ],
    "contract": [
        (
            "inbound",
            "2026-07-20",
            "Contract renewal comments",
            "Our legal team has comments on the liability clause in the renewal. Until the contract renewal is signed we will order on spot terms only.",
        )
    ],
    "none": [
        ("inbound", "2026-09-02", "Invoice copy request", "Could you resend the invoice for order SO-004211? Thanks.")
    ],
}


def _emails(
    db: Session, org_id: str, by_scen: dict[str, CrmCustomer], all_c: list[CrmCustomer], rng: random.Random
) -> int:
    n = 0
    for scen, items in EMAILS.items():
        c = by_scen[scen]
        for direction, d, subject, body in items:
            sender = c.contact_email if direction == "inbound" else "sales@acme.example"
            recip = "sales@acme.example" if direction == "inbound" else c.contact_email
            db.add(
                EmailRecord(
                    org_id=org_id,
                    customer_id=c.id,
                    direction=direction,
                    sender=sender,
                    recipient=recip,
                    subject=subject,
                    body=body,
                    sent_at=datetime.fromisoformat(d).replace(hour=10, tzinfo=UTC),
                )
            )
            n += 1
    for c in all_c:
        d = AS_OF - timedelta(days=rng.randint(5, 120))
        db.add(
            EmailRecord(
                org_id=org_id,
                customer_id=c.id,
                direction="outbound",
                sender="sales@acme.example",
                recipient=c.contact_email,
                subject="Order confirmation",
                body=f"Thank you for your order. Your account manager is {c.account_manager}.",
                sent_at=datetime(d.year, d.month, d.day, 9, tzinfo=UTC),
            )
        )
        n += 1
    return n


def _pdf_bytes() -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    for page in bd.NCR_PDF_PAGES:
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 6, page)
    return bytes(pdf.output())


def _docx_bytes() -> bytes:
    import docx

    d = docx.Document()
    d.add_heading(bd.HANDBOOK_DOCX_TITLE, level=1)
    for heading, paras in bd.HANDBOOK_DOCX:
        d.add_heading(heading, level=2)
        for p in paras:
            d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _xlsx_bytes() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Q3 2026"
    for row in bd.DELIVERY_XLSX_ROWS:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _title(path: Path) -> str:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    return first.lstrip("# ").strip() if path.suffix == ".md" else path.stem.replace("_", " ").title()


def add_document(
    db: Session,
    storage: ObjectStorage,
    org: Organization,
    filename: str,
    title: str,
    data: bytes,
    source: str = "seed",
    uploaded_by: str | None = None,
) -> Document:
    kind = validate_upload(filename, data, 50 * 1024 * 1024)
    sha = hashlib.sha256(data).hexdigest()
    key = f"{org.id}/{sha}.{kind.ext}"
    storage.put(key, data)
    doc = Document(
        org_id=org.id,
        title=title,
        source_type=source,
        source_uri=filename,
        mime_type=kind.mime,
        sha256=sha,
        size_bytes=len(data),
        storage_path=key,
        uploaded_by=uploaded_by,
    )
    db.add(doc)
    db.flush()
    enqueue(db, doc)
    return doc


def _documents(db: Session, acme: Organization, globex: Organization, storage: ObjectStorage) -> int:
    n = 0
    for p in sorted(SEED_DIR.iterdir()):
        if p.suffix in (".md", ".txt", ".csv") and p.name != "README.md":
            add_document(db, storage, acme, p.name, _title(p), p.read_bytes())
            n += 1
    add_document(db, storage, acme, "ncr_harbor_marine.pdf", bd.NCR_PDF_TITLE, _pdf_bytes())
    add_document(db, storage, acme, "customer_service_handbook.docx", bd.HANDBOOK_DOCX_TITLE, _docx_bytes())
    add_document(db, storage, acme, "delivery_performance_q3.xlsx", bd.DELIVERY_XLSX_TITLE, _xlsx_bytes())
    add_document(
        db,
        storage,
        globex,
        "globex_confidential.md",
        "Globex Confidential Pricing",
        b"# Globex Confidential Pricing\n\nGlobex internal margin target for Electrical is 41 percent. Confidential to Globex.\n",
    )
    db.commit()
    assert set(EXT_BY_MIME)  # keep import used
    return n + 4


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="truncate all tables first")
    args = ap.parse_args()
    with session_factory()() as db:
        if args.reset:
            reset(db)
        print(seed(db, get_storage()))


if __name__ == "__main__":
    main()
