"""Typed QueryPlan -- the ONLY thing a planner (local rules or LLM) is allowed to produce.

SQL is generated from a plan by app.services.compiler, never by the planner.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FilterOp = Literal["eq", "neq", "in", "gt", "gte", "lt", "lte"]


class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(description="dimension name (WHERE) or metric name (HAVING)")
    kind: Literal["dimension", "metric"] = "dimension"
    op: FilterOp = "eq"
    value: str | float | list[str]

    @model_validator(mode="after")
    def _check_value(self) -> "Filter":
        if self.op == "in" and not isinstance(self.value, list):
            raise ValueError("op 'in' requires a list value")
        if self.op in ("gt", "gte", "lt", "lte") and not isinstance(self.value, int | float):
            raise ValueError(f"op '{self.op}' requires a numeric value")
        if isinstance(self.value, list) and not 1 <= len(self.value) <= 50:
            raise ValueError("list filter must have 1..50 values")
        return self


class TimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: date = Field(description="inclusive")
    end: date = Field(description="exclusive")
    label: str = ""

    @model_validator(mode="after")
    def _check_order(self) -> "TimeRange":
        if self.end <= self.start:
            raise ValueError("time_range.end must be after start")
        return self


class OrderBy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    direction: Literal["asc", "desc"] = "desc"


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metrics: list[str] = Field(min_length=1, max_length=4)
    dimensions: list[str] = Field(default_factory=list, max_length=2)
    filters: list[Filter] = Field(default_factory=list, max_length=10)
    time_range: TimeRange | None = None
    order_by: list[OrderBy] = Field(default_factory=list, max_length=3)
    limit: int = Field(default=100, ge=1, le=100000)
    assumptions: list[str] = Field(default_factory=list)


class Clarification(BaseModel):
    question: str
    options: list[str]


class PlannerOutcome(BaseModel):
    """What a planner returns: exactly one of plan / clarification / rejection."""

    kind: Literal["plan", "clarify", "reject"]
    plan: QueryPlan | None = None
    clarification: Clarification | None = None
    reason: str | None = None
