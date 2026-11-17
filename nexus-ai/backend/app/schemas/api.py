from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 -- OAuth token type, not a secret


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: str
    org_id: str


class MeOut(UserOut):
    org_name: str
    llm_provider: str
    embedding_provider: str


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = None


class AskOut(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    citations: list[dict[str, Any]]
    contexts: list[str]
    retrieval: list[dict[str, Any]]
    insufficient_evidence: bool
    provider: str
    model: str
    usage: dict[str, Any]
    latency_ms: int


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    citations: list[dict[str, Any]]
    meta: dict[str, Any]
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    source_type: str
    source_uri: str | None
    mime_type: str
    size_bytes: int
    status: str
    error: str | None
    page_count: int | None
    chunk_count: int
    meta: dict[str, Any]
    created_at: datetime


class UrlIngestIn(BaseModel):
    url: HttpUrl
    title: str | None = Field(default=None, max_length=300)


class WorkflowIn(BaseModel):
    goal: str = Field(min_length=10, max_length=2000)


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    seq: int
    name: str
    agent: str
    status: str
    attempts: int
    tool_calls: list[dict[str, Any]]
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    goal: str
    kind: str
    status: str
    plan: list[str]
    error: str | None
    tokens_used: int
    token_budget: int
    created_at: datetime
    finished_at: datetime | None


class RunDetailOut(RunOut):
    report: dict[str, Any] | None
    steps: list[StepOut]
    approvals: list["ApprovalOut"]


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_id: str | None
    action: str
    payload: dict[str, Any]
    rationale: str | None
    status: str
    decided_by: str | None
    decided_at: datetime | None
    decision_note: str | None
    result: dict[str, Any] | None
    created_at: datetime


class DecisionIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=4000)


class MemoryIn(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_ .-]+$")
    value: str = Field(min_length=1, max_length=1000)


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    key: str
    value: str
    source: str
    created_at: datetime


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    outcome: str
    details: dict[str, Any]
    request_id: str | None
    created_at: datetime


RunDetailOut.model_rebuild()
