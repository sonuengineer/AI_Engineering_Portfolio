"""Provider abstraction shared by run targets and the LLM-as-judge evaluator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderError(Exception):
    """Non-retryable provider failure."""


class TransientProviderError(ProviderError):
    """Retryable failure (timeouts, 429, 5xx)."""


class ProviderNotConfigured(ProviderError):
    """Provider requires a key/SDK that is not available."""


@dataclass
class GenerationRequest:
    system_prompt: str
    user_prompt: str
    params: dict[str, Any] = field(default_factory=dict)
    json_schema: dict[str, Any] | None = None
    timeout_s: float = 30.0
    # Only used by deterministic providers (local / mock_scripted); real models never see it.
    case: dict[str, Any] | None = None


@dataclass
class GenerationResult:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_estimated: bool = False
    parsed: Any = None
    notes: str = ""


class LLMProvider(Protocol):
    name: str
    is_real_llm: bool

    def generate(self, request: GenerationRequest, model: str) -> GenerationResult: ...


def estimate_tokens(text: str) -> int:
    """Rough heuristic (~4 chars/token). Always flagged as tokens_estimated=True."""
    return max(1, (len(text) + 3) // 4) if text else 0


def try_parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None
