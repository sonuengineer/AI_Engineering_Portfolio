"""Local demo connectors over the seeded CRM/ERP/email tables.

Each function is org-scoped. A production deployment would implement the same functions
against Salesforce/SAP/Gmail APIs; callers depend only on these signatures.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models import CrmCustomer, EmailRecord, ErpOrder, ErpQuotation


def as_of_date(db: Session, org_id: str) -> date:
    """Analysis reference date = latest order date for the org (keeps demo reproducible)."""
    d = db.scalar(select(func.max(ErpOrder.order_date)).where(ErpOrder.org_id == org_id))
    return d or date.today()


def _months_back(d: date, months: int) -> date:
    return d - timedelta(days=round(months * 30.44))


def search_customers(db: Session, org_id: str, query: str | None, limit: int) -> list[dict[str, Any]]:
    stmt = select(CrmCustomer).where(CrmCustomer.org_id == org_id)
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(CrmCustomer.name).like(like),
                func.lower(CrmCustomer.industry).like(like),
                func.lower(CrmCustomer.region).like(like),
                func.lower(CrmCustomer.code).like(like),
            )
        )
    rows = db.scalars(stmt.order_by(CrmCustomer.name).limit(limit))
    return [_cust(c) for c in rows]


def _cust(c: CrmCustomer) -> dict[str, Any]:
    return {
        "customer_id": c.id,
        "code": c.code,
        "name": c.name,
        "industry": c.industry,
        "region": c.region,
        "tier": c.tier,
        "account_manager": c.account_manager,
        "contact_name": c.contact_name,
        "contact_email": c.contact_email,
    }


def top_customers_with_trend(db: Session, org_id: str, top_n: int, window_months: int) -> list[dict[str, Any]]:
    """Top N customers by revenue over the two windows combined, with prior vs recent revenue."""
    end = as_of_date(db, org_id)
    mid = _months_back(end, window_months)
    start = _months_back(mid, window_months)
    done = ErpOrder.status == "completed"
    recent = func.coalesce(func.sum(case((and_(ErpOrder.order_date > mid, done), ErpOrder.amount))), 0)
    prior = func.coalesce(func.sum(case((and_(ErpOrder.order_date <= mid, done), ErpOrder.amount))), 0)
    delay_recent = func.coalesce(func.avg(case((ErpOrder.order_date > mid, ErpOrder.delivery_delay_days))), 0)
    delay_prior = func.coalesce(func.avg(case((ErpOrder.order_date <= mid, ErpOrder.delivery_delay_days))), 0)
    stmt = (
        select(
            CrmCustomer, recent.label("recent"), prior.label("prior"), delay_recent.label("dr"), delay_prior.label("dp")
        )
        .join(ErpOrder, ErpOrder.customer_id == CrmCustomer.id)
        .where(
            CrmCustomer.org_id == org_id,
            ErpOrder.org_id == org_id,
            ErpOrder.order_date > start,
            ErpOrder.order_date <= end,
        )
        .group_by(CrmCustomer.id)
        .order_by((recent + prior).desc())
        .limit(top_n)
    )
    out = []
    for c, r, p, dr, dp in db.execute(stmt).all():
        r, p = Decimal(r), Decimal(p)
        change = float((r - p) / p * 100) if p else 0.0
        out.append(
            {
                **_cust(c),
                "recent_revenue": float(r),
                "prior_revenue": float(p),
                "change_pct": round(change, 1),
                "avg_delay_recent": round(float(dr), 1),
                "avg_delay_prior": round(float(dp), 1),
                "window_months": window_months,
                "window": {"start": start.isoformat(), "mid": mid.isoformat(), "end": end.isoformat()},
            }
        )
    return out


def customer_orders(db: Session, org_id: str, customer_id: str, months: int) -> dict[str, Any]:
    end = as_of_date(db, org_id)
    start = _months_back(end, months)
    rows = db.execute(
        select(
            func.date_trunc("month", ErpOrder.order_date).label("m"),
            func.count(),
            func.sum(ErpOrder.amount),
            func.avg(ErpOrder.delivery_delay_days),
        )
        .where(
            ErpOrder.org_id == org_id,
            ErpOrder.customer_id == customer_id,
            ErpOrder.status == "completed",
            ErpOrder.order_date > start,
        )
        .group_by("m")
        .order_by("m")
    ).all()
    return {
        "customer_id": customer_id,
        "months": months,
        "monthly": [
            {
                "month": m.date().isoformat()[:7],
                "orders": n,
                "revenue": float(s or 0),
                "avg_delay_days": round(float(d or 0), 1),
            }
            for m, n, s, d in rows
        ],
    }


def pending_quotations(db: Session, org_id: str, customer_id: str | None) -> list[dict[str, Any]]:
    stmt = select(ErpQuotation).where(ErpQuotation.org_id == org_id, ErpQuotation.status == "pending")
    if customer_id:
        stmt = stmt.where(ErpQuotation.customer_id == customer_id)
    return [
        {
            "quote_number": q.quote_number,
            "customer_id": q.customer_id,
            "amount": float(q.amount),
            "product_line": q.product_line,
            "issued_on": q.issued_on.isoformat(),
            "valid_until": q.valid_until.isoformat(),
        }
        for q in db.scalars(stmt.order_by(ErpQuotation.issued_on))
    ]


def search_emails(
    db: Session, org_id: str, customer_id: str | None, query: str | None, limit: int
) -> list[dict[str, Any]]:
    stmt = select(EmailRecord).where(EmailRecord.org_id == org_id)
    if customer_id:
        stmt = stmt.where(EmailRecord.customer_id == customer_id)
    if query:
        terms = [t for t in query.lower().split() if len(t) > 2][:8]
        if terms:
            stmt = stmt.where(
                or_(*[func.lower(EmailRecord.subject + " " + EmailRecord.body).like(f"%{t}%") for t in terms])
            )
    rows = db.scalars(stmt.order_by(EmailRecord.sent_at.desc()).limit(limit))
    return [
        {
            "id": e.id,
            "customer_id": e.customer_id,
            "direction": e.direction,
            "sender": e.sender,
            "subject": e.subject,
            "body": e.body,
            "sent_at": e.sent_at.isoformat(),
        }
        for e in rows
    ]
