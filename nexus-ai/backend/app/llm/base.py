"""Provider-neutral LLM interfaces.

Every call returns a Pydantic-validated object plus a Usage record. The `local` provider is a
deterministic rule-based adapter used when no API key is configured; it is always reported as
provider="local" so nothing downstream can mistake it for a real model call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
Tier = Literal["fast", "strong"]

# USD per 1M tokens (input, output). Estimates only -- verify against current provider pricing.
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


def estimate_tokens(text: str) -> int:
    """Rough heuristic (~4 chars per token). Used for budgets when a provider gives no counts."""
    return max(1, len(text) // 4)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICE_TABLE.get(model, (0.0, 0.0))
    return round((input_tokens * price_in + output_tokens * price_out) / 1_000_000, 6)


@dataclass
class Usage:
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0
    tokens_are_estimates: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "latency_ms": self.latency_ms,
            "tokens_are_estimates": self.tokens_are_estimates,
        }


@dataclass
class LLMRequest:
    """A structured-generation request.

    `task` names the job (e.g. "answer_question"); `system`/`user` are the prompts sent to real
    models; `payload` is the same information as structured data, used by the local adapter.
    """

    task: str
    system: str
    user: str
    payload: dict[str, Any] = field(default_factory=dict)
    tier: Tier = "fast"


class StructuredOutputError(RuntimeError):
    pass


class LLMProvider(Protocol):
    name: str

    def generate(self, request: LLMRequest, schema: type[T]) -> tuple[T, Usage]: ...


class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
