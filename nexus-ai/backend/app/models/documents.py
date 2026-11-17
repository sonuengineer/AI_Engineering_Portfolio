from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import IdMixin, TimestampMixin

EMBEDDING_DIM = 384


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(20))  # upload | url | seed
    source_uri: Mapped[str | None] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(120))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|processing|ready|failed
    error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Chunk(IdMixin, Base):
    __tablename__ = "chunks"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    token_estimate: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('english', text)", persisted=True))
    flags: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class IngestionJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_jobs"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
