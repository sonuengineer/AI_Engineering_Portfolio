"""HTTP request/response schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.plan import Clarification, QueryPlan


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class MeResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    org_id: int
    org_name: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class Validation(BaseModel):
    ok: bool
    issues: list[str] = Field(default_factory=list)


class Provenance(BaseModel):
    columns: list[str] = Field(default_factory=list)
    row_indexes: list[int] = Field(default_factory=list)
    note: str = ""


class ChartSpec(BaseModel):
    type: Literal["line", "bar", "table"]
    x: str | None = None
    y: list[str] = Field(default_factory=list)
    series: str | None = None


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class AskResponse(BaseModel):
    """Contract fixed by MASTER_ARCHITECTURE.md section 3 (extra fields are additive)."""

    status: Literal["answered", "needs_clarification", "rejected"]
    plan: dict[str, Any] | None = None
    sql: str | None = None
    validation: Validation = Field(default_factory=lambda: Validation(ok=False))
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    insight: str | None = None
    clarification: Clarification | None = None
    rejection_reason: str | None = None
    provider: str
    model: str | None = None
    latency_ms: int = 0
    # additive fields
    query_id: int | None = None
    chart: ChartSpec | None = None
    insight_provenance: list[Provenance] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    question: str
    status: str
    sql: str | None
    row_count: int
    provider: str
    latency_ms: int
    created_at: datetime
    user_id: int


class SavedReportCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=500)
    plan: QueryPlan


class SavedReportUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SavedReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    question: str
    plan: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    user_id: int
