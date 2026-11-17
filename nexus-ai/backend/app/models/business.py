"""Synthetic CRM / ERP / email data used by the local demo connectors."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import IdMixin


class CrmCustomer(IdMixin, Base):
    __tablename__ = "crm_customers"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(80))
    account_manager: Mapped[str] = mapped_column(String(120))
    contact_name: Mapped[str] = mapped_column(String(120))
    contact_email: Mapped[str] = mapped_column(String(320))
    tier: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)


class ErpOrder(IdMixin, Base):
    __tablename__ = "erp_orders"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("crm_customers.id"), index=True)
    order_number: Mapped[str] = mapped_column(String(30))
    order_date: Mapped[date] = mapped_column(Date, index=True)
    product_line: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20))  # completed | cancelled
    delivery_delay_days: Mapped[int] = mapped_column(Integer, default=0)


class ErpQuotation(IdMixin, Base):
    __tablename__ = "erp_quotations"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("crm_customers.id"), index=True)
    quote_number: Mapped[str] = mapped_column(String(30))
    issued_on: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20))  # pending | accepted | rejected | expired
    product_line: Mapped[str] = mapped_column(String(80))


class EmailRecord(IdMixin, Base):
    __tablename__ = "email_records"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("crm_customers.id"), index=True)
    direction: Mapped[str] = mapped_column(String(10))  # inbound | outbound
    sender: Mapped[str] = mapped_column(String(320))
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
