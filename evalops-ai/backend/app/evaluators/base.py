"""Evaluator data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseData:
    external_id: str
    input: str
    expected_output: str | None = None
    reference_contexts: list[str] = field(default_factory=list)
    expected_citations: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TargetOutput:
    """Normalized output of any target (LLM, NEXUS, DATAWISE)."""

    text: str = ""
    json: Any = None
    citations: list[str] = field(default_factory=list)  # document ids returned by the target
    contexts: list[str] = field(default_factory=list)  # retrieved texts given to the generator
    status: str | None = None  # e.g. answered | needs_clarification | rejected
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] | None = None
    latency_ms: float | None = None
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_estimated: bool = False
    provider: str | None = None
    model: str | None = None
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "json": self.json,
            "citations": self.citations,
            "contexts": self.contexts,
            "status": self.status,
            "sql": self.sql,
            "columns": self.columns,
            "rows": self.rows,
            "provider": self.provider,
            "model": self.model,
        }


@dataclass
class EvalOutcome:
    metric: str
    status: str = "scored"  # scored | skipped | error
    value: float | None = None
    passed: bool | None = None
    is_estimate: bool = False
    explanation: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def skipped(cls, metric: str, reason: str, *, is_estimate: bool = False) -> EvalOutcome:
        return cls(metric=metric, status="skipped", explanation=reason, is_estimate=is_estimate)
