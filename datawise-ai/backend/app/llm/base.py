"""Planner provider abstraction. Every provider returns a PlannerOutcome (typed) + Usage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas.plan import PlannerOutcome


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class ProviderError(Exception):
    """Provider failed or returned unusable structured output after one repair retry."""


class PlannerProvider(ABC):
    name: str = "base"
    model: str | None = None

    @abstractmethod
    def plan(self, question: str) -> tuple[PlannerOutcome, Usage]:
        """Turn a natural-language question into a typed outcome. Must never return SQL."""
