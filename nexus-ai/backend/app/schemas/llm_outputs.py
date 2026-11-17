"""Structured outputs requested from LLM providers (validated with Pydantic)."""

from typing import Literal

from pydantic import BaseModel, Field


class GroundedAnswer(BaseModel):
    answer: str = Field(description="Answer text with [n] citation markers referring to contexts")
    cited_context_ids: list[int] = Field(default_factory=list)
    insufficient_evidence: bool = False


AgentName = Literal["data_agent", "research_agent", "analysis_agent", "report_agent", "action_agent"]


class WorkflowPlan(BaseModel):
    intent: Literal["customer_decline_investigation", "document_question", "unsupported"]
    steps: list[AgentName]
    top_n: int = Field(default=10, ge=1, le=50)
    lookback_months: int = Field(default=6, ge=1, le=24)
    rationale: str


class Evidence(BaseModel):
    statement: str
    source: str  # e.g. "erp_orders", "email:<id>", "document:<id>#p2"


class Hypothesis(BaseModel):
    statement: str
    confidence: Literal["low", "medium", "high"]
    supporting_sources: list[str]


class CustomerFinding(BaseModel):
    customer_id: str
    customer_name: str
    evidence: list[Evidence]
    hypotheses: list[Hypothesis]
    recommended_action: str


class EvidenceAnalysis(BaseModel):
    summary: str
    findings: list[CustomerFinding]


class EmailDraft(BaseModel):
    subject: str = Field(max_length=200)
    body: str = Field(max_length=4000)
