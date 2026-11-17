"""SQLAlchemy ORM models. Every tenant-owned row carries org_id."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Org(TimestampMixin, Base):
    __tablename__ = "orgs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="member")  # admin|member|viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("org_id", "slug"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")


class DatasetVersion(TimestampMixin, Base):
    """Immutable snapshot of a dataset; content_hash = sha256 over canonical case JSON."""

    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    source_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)


class TestCase(Base):
    __tablename__ = "test_cases"
    __test__ = False  # keep pytest from collecting this class
    __table_args__ = (UniqueConstraint("dataset_version_id", "external_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[str] = mapped_column(Text)
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_contexts: Mapped[list[str]] = mapped_column(JSONB, default=list)
    expected_citations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class PromptTemplate(TimestampMixin, Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")


class PromptVersion(TimestampMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("template_id", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompt_templates.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    user_template: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))


class ModelConfig(TimestampMixin, Base):
    __tablename__ = "model_configs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(40))  # local|mock_scripted|gemini|openai
    model: Mapped[str] = mapped_column(String(200))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    price_in_per_1k: Mapped[float] = mapped_column(Float, default=0.0)
    price_out_per_1k: Mapped[float] = mapped_column(Float, default=0.0)


class Target(TimestampMixin, Base):
    """kind=llm -> model_config + prompt_version; kind=http_nexus|http_datawise -> config with *_env refs."""

    __tablename__ = "targets"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40))
    model_config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True
    )
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="SET NULL"), nullable=True
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class EvaluatorConfig(TimestampMixin, Base):
    __tablename__ = "evaluator_configs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(20))  # deterministic|judge
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    gating: Mapped[bool] = mapped_column(Boolean, default=True)  # counts toward case pass/fail


class Experiment(TimestampMixin, Base):
    __tablename__ = "experiments"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)


class Run(TimestampMixin, Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id"), index=True)
    label: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued|running|completed|failed
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    dataset_hash: Mapped[str] = mapped_column(String(64))
    seed: Mapped[int] = mapped_column(Integer, default=0)
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class RunResult(TimestampMixin, Base):
    __tablename__ = "run_results"
    __table_args__ = (UniqueConstraint("run_id", "test_case_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tokens_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    trace_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class MetricScore(TimestampMixin, Base):
    __tablename__ = "metric_scores"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    run_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run_results.id", ondelete="CASCADE"), index=True)
    evaluator_config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluator_configs.id", ondelete="SET NULL"), nullable=True
    )
    metric: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), default="scored")  # scored|skipped|error
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_estimate: Mapped[bool] = mapped_column(Boolean, default=False)
    gating: Mapped[bool] = mapped_column(Boolean, default=True)
    explanation: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Trace(TimestampMixin, Base):
    __tablename__ = "traces"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Span(Base):
    __tablename__ = "spans"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("traces.id", ondelete="CASCADE"), index=True)
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    span_type: Mapped[str] = mapped_column(String(20))  # prompt|model_call|retrieval|tool|http|eval
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class AuditEvent(TimestampMixin, Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(60), default="")
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
