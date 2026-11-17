"""Pydantic request/response models."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    display_name: str
    role: str


class UserCreate(BaseModel):
    email: str = Field(max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(default="", max_length=200)
    role: Literal["admin", "member", "viewer"] = "member"


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str = Field(default="", max_length=2000)


class ProjectOut(ORM):
    id: uuid.UUID
    name: str
    slug: str
    description: str
    created_at: dt.datetime


class DatasetIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class DatasetVersionOut(ORM):
    id: uuid.UUID
    dataset_id: uuid.UUID
    version: int
    content_hash: str
    case_count: int
    notes: str
    source_filename: str | None
    created_at: dt.datetime


class DatasetOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str
    created_at: dt.datetime
    versions: list[DatasetVersionOut] = []


class TestCaseOut(ORM):
    __test__ = False
    id: uuid.UUID
    external_id: str
    position: int
    input: str
    expected_output: str | None
    reference_contexts: list[str]
    expected_citations: list[str]
    tags: list[str]
    meta: dict[str, Any] = Field(serialization_alias="metadata")


class PromptTemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class PromptVersionIn(BaseModel):
    system_prompt: str = Field(default="", max_length=20000)
    user_template: str = Field(min_length=1, max_length=20000)


class PromptVersionOut(ORM):
    id: uuid.UUID
    template_id: uuid.UUID
    version: int
    system_prompt: str
    user_template: str
    content_hash: str
    created_at: dt.datetime


class PromptTemplateOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str
    created_at: dt.datetime
    versions: list[PromptVersionOut] = []


class ModelConfigIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: Literal["local", "mock_scripted", "gemini", "openai"]
    model: str = Field(min_length=1, max_length=200)
    params: dict[str, Any] = {}
    price_in_per_1k: float = Field(default=0.0, ge=0)
    price_out_per_1k: float = Field(default=0.0, ge=0)


class ModelConfigOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    provider: str
    model: str
    params: dict[str, Any]
    price_in_per_1k: float
    price_out_per_1k: float


class TargetIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["llm", "http_nexus", "http_datawise"]
    model_config_id: uuid.UUID | None = None
    prompt_version_id: uuid.UUID | None = None
    config: dict[str, Any] = {}


class TargetOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    kind: str
    model_config_id: uuid.UUID | None
    prompt_version_id: uuid.UUID | None
    config: dict[str, Any]


class EvaluatorIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=60)
    params: dict[str, Any] = {}
    threshold: float | None = None
    gating: bool = True


class EvaluatorOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    type: str
    kind: str
    params: dict[str, Any]
    threshold: float | None
    gating: bool


class ExperimentIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    dataset_id: uuid.UUID | None = None


class ExperimentOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str
    dataset_id: uuid.UUID | None
    created_at: dt.datetime


class RunCreate(BaseModel):
    project_id: uuid.UUID
    dataset_version_id: uuid.UUID
    target_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    evaluator_ids: list[uuid.UUID] = Field(default=[], max_length=50)
    experiment_id: uuid.UUID | None = None
    label: str = Field(default="", max_length=200)
    concurrency: int = Field(default=4, ge=1, le=32)
    timeout_s: float = Field(default=30.0, ge=1, le=300)
    max_retries: int = Field(default=2, ge=0, le=5)
    seed: int = 0


class SpanOut(ORM):
    id: uuid.UUID
    parent_span_id: uuid.UUID | None
    name: str
    span_type: str
    started_at: dt.datetime
    ended_at: dt.datetime | None
    duration_ms: float | None
    status: str
    attributes: dict[str, Any]


class TraceOut(ORM):
    id: uuid.UUID
    run_id: uuid.UUID | None
    name: str
    started_at: dt.datetime
    ended_at: dt.datetime | None
    duration_ms: float | None
    status: str
    attributes: dict[str, Any]
    spans: list[SpanOut] = []


class AuditOut(ORM):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict[str, Any]
    request_id: str | None
    created_at: dt.datetime
