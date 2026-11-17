from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import IdMixin, TimestampMixin


class Conversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text)


class Message(IdMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class MemoryItem(IdMixin, TimestampMixin, Base):
    """Controlled long-term memory: explicit, user-visible, deletable facts/preferences."""

    __tablename__ = "memory_items"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_memory_user_key"),)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="user")
