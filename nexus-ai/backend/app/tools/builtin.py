"""Built-in tools. Import this module to register them."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.connectors import business as biz
from app.core.errors import Conflict, NotFound
from app.models import ApprovalRequest, CrmCustomer, OutboxMessage
from app.services.retrieval import hybrid_search
from app.tools.registry import ToolContext, ToolSpec, register


# ---------- schemas ----------
class SearchCustomersIn(BaseModel):
    query: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=20, ge=1, le=100)


class CustomerList(BaseModel):
    customers: list[dict[str, Any]]


class TopCustomersIn(BaseModel):
    top_n: int = Field(default=10, ge=1, le=50)
    window_months: int = Field(default=6, ge=1, le=12)


class CustomerOrdersIn(BaseModel):
    customer_id: str
    months: int = Field(default=12, ge=1, le=36)


class CustomerOrdersOut(BaseModel):
    customer_id: str
    months: int
    monthly: list[dict[str, Any]]


class SearchDocumentsIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(default=5, ge=1, le=20)


class DocumentHits(BaseModel):
    hits: list[dict[str, Any]]


class SearchEmailsIn(BaseModel):
    customer_id: str | None = None
    query: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


class EmailList(BaseModel):
    emails: list[dict[str, Any]]


class PendingQuotesIn(BaseModel):
    customer_id: str | None = None


class QuoteList(BaseModel):
    quotations: list[dict[str, Any]]


class DraftEmailIn(BaseModel):
    customer_id: str
    subject: str = Field(max_length=200)
    body: str = Field(max_length=4000)
    rationale: str = Field(max_length=2000)


class DraftEmailOut(BaseModel):
    approval_id: str
    status: str
    to: str


class SendEmailIn(BaseModel):
    to: EmailStr
    subject: str = Field(max_length=200)
    body: str = Field(max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=120)


class SendEmailOut(BaseModel):
    outbox_id: str
    deduplicated: bool


class ReportIn(BaseModel):
    title: str = Field(max_length=200)
    sections: list[dict[str, Any]]


class ReportOut(BaseModel):
    title: str
    markdown: str


# ---------- implementations ----------
def _search_customers(ctx: ToolContext, a: SearchCustomersIn) -> CustomerList:
    return CustomerList(customers=biz.search_customers(ctx.db, ctx.user.org_id, a.query, a.limit))


def _top_customers(ctx: ToolContext, a: TopCustomersIn) -> CustomerList:
    return CustomerList(customers=biz.top_customers_with_trend(ctx.db, ctx.user.org_id, a.top_n, a.window_months))


def _customer_orders(ctx: ToolContext, a: CustomerOrdersIn) -> CustomerOrdersOut:
    cust = ctx.db.get(CrmCustomer, a.customer_id)
    if cust is None or cust.org_id != ctx.user.org_id:
        raise NotFound("Customer not found")
    return CustomerOrdersOut(**biz.customer_orders(ctx.db, ctx.user.org_id, a.customer_id, a.months))


def _search_documents(ctx: ToolContext, a: SearchDocumentsIn) -> DocumentHits:
    hits = hybrid_search(ctx.db, ctx.user.org_id, a.query, k=a.k)
    return DocumentHits(
        hits=[
            {
                "chunk_id": h.chunk_id,
                "document_id": h.document_id,
                "document_title": h.document_title,
                "page": h.page,
                "text": h.text,
                "score": h.rerank_score,
                "flagged": bool(h.flags.get("suspicious_instructions")),
            }
            for h in hits
        ]
    )


def _search_emails(ctx: ToolContext, a: SearchEmailsIn) -> EmailList:
    return EmailList(emails=biz.search_emails(ctx.db, ctx.user.org_id, a.customer_id, a.query, a.limit))


def _pending_quotes(ctx: ToolContext, a: PendingQuotesIn) -> QuoteList:
    return QuoteList(quotations=biz.pending_quotations(ctx.db, ctx.user.org_id, a.customer_id))


def _draft_email(ctx: ToolContext, a: DraftEmailIn) -> DraftEmailOut:
    """Creates a pending approval request. Never sends anything."""
    cust = ctx.db.get(CrmCustomer, a.customer_id)
    if cust is None or cust.org_id != ctx.user.org_id:
        raise NotFound("Customer not found")
    key = "email:" + hashlib.sha256(f"{ctx.run_id}|{cust.id}|{a.subject}".encode()).hexdigest()[:40]
    existing = ctx.db.scalar(select(ApprovalRequest).where(ApprovalRequest.idempotency_key == key))
    if existing:
        return DraftEmailOut(approval_id=existing.id, status=existing.status, to=cust.contact_email)
    req = ApprovalRequest(
        org_id=ctx.user.org_id,
        run_id=ctx.run_id,
        action="send_email",
        payload={
            "to": cust.contact_email,
            "subject": a.subject,
            "body": a.body,
            "customer_id": cust.id,
            "customer_name": cust.name,
        },
        rationale=a.rationale,
        idempotency_key=key,
        requested_by=ctx.user.id,
    )
    ctx.db.add(req)
    ctx.db.flush()
    return DraftEmailOut(approval_id=req.id, status=req.status, to=cust.contact_email)


def _send_email(ctx: ToolContext, a: SendEmailIn) -> SendEmailOut:
    """Local outbox connector. Idempotent: same key -> same message, never a duplicate send."""
    existing = ctx.db.scalar(select(OutboxMessage).where(OutboxMessage.idempotency_key == a.idempotency_key))
    if existing:
        return SendEmailOut(outbox_id=existing.id, deduplicated=True)
    if ctx.approved_action_id is None:
        raise Conflict("send_email requires an approved action")
    msg = OutboxMessage(
        org_id=ctx.user.org_id,
        idempotency_key=a.idempotency_key,
        to_address=a.to,
        subject=a.subject,
        body=a.body,
        approval_id=ctx.approved_action_id,
    )
    ctx.db.add(msg)
    ctx.db.flush()
    return SendEmailOut(outbox_id=msg.id, deduplicated=False)


def _generate_report(ctx: ToolContext, a: ReportIn) -> ReportOut:
    lines = [f"# {a.title}", ""]
    for s in a.sections:
        lines.append(f"## {s.get('heading', 'Section')}")
        lines.append(str(s.get("body", "")))
        lines.append("")
    return ReportOut(title=a.title, markdown="\n".join(lines))


register(
    ToolSpec(
        "search_customers",
        "Search CRM customers by name/industry/region/code.",
        SearchCustomersIn,
        CustomerList,
        _search_customers,
    )
)
register(
    ToolSpec(
        "get_top_customers",
        "Top N customers by revenue with prior-vs-recent trend.",
        TopCustomersIn,
        CustomerList,
        _top_customers,
    )
)
register(
    ToolSpec(
        "get_customer_orders",
        "Monthly ERP order history for one customer.",
        CustomerOrdersIn,
        CustomerOrdersOut,
        _customer_orders,
    )
)
register(
    ToolSpec(
        "search_documents",
        "Hybrid semantic+keyword search over indexed documents.",
        SearchDocumentsIn,
        DocumentHits,
        _search_documents,
    )
)
register(
    ToolSpec(
        "search_emails", "Search email records, optionally for one customer.", SearchEmailsIn, EmailList, _search_emails
    )
)
register(
    ToolSpec("get_pending_quotations", "List pending ERP quotations.", PendingQuotesIn, QuoteList, _pending_quotes)
)
register(ToolSpec("generate_report", "Render a markdown report from sections.", ReportIn, ReportOut, _generate_report))
register(
    ToolSpec(
        "draft_followup_email",
        "Draft a customer email; creates an approval request.",
        DraftEmailIn,
        DraftEmailOut,
        _draft_email,
        side_effect="write",
    )
)
register(
    ToolSpec(
        "send_email",
        "Send an email via the outbox connector (approval required).",
        SendEmailIn,
        SendEmailOut,
        _send_email,
        min_role="manager",
        side_effect="external",
        requires_approval=True,
        mcp_exposed=False,
    )
)
