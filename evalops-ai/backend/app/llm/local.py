"""Deterministic local adapters. These are NOT language models.

- `local` (models: local-extractive-v1, local-echo-v1): rule-based. The extractive mode
  returns the context sentence with the highest token overlap with the question; echo mode
  returns the input. Used for keyless demos/tests; the UI labels it "Deterministic local adapter".
- `mock_scripted`: returns outputs scripted inside the dataset case metadata
  (`metadata.scripted_outputs[<script>]`). Used for reproducible regression demos. Its scores
  measure the script, not any model.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.llm.base import (
    GenerationRequest,
    GenerationResult,
    ProviderError,
    estimate_tokens,
    try_parse_json,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are", "was", "what", "which",
    "who", "how", "does", "do", "did", "with", "by", "at", "be", "it", "this", "that", "from", "as", "our",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP}


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


class LocalProvider:
    name = "local"
    is_real_llm = False

    def generate(self, request: GenerationRequest, model: str) -> GenerationResult:
        case = request.case or {}
        question = str(case.get("input") or request.user_prompt)
        mode = "echo" if "echo" in model else "extractive"
        if mode == "echo":
            text = question
        else:
            contexts: list[str] = list(case.get("reference_contexts") or [])
            sentences = [s for c in contexts for s in _split_sentences(c)]
            q = _tokens(question)
            best, best_score = "", 0.0
            for s in sentences:
                st = _tokens(s)
                score = len(q & st) / (len(q) or 1)
                if score > best_score:
                    best, best_score = s, score
            text = best if best else "I could not find this in the provided context."
        return GenerationResult(
            text=text,
            provider=self.name,
            model=model,
            input_tokens=estimate_tokens(request.system_prompt + request.user_prompt),
            output_tokens=estimate_tokens(text),
            tokens_estimated=True,
            parsed=try_parse_json(text),
            notes=f"deterministic local adapter ({mode}); not an LLM",
        )


class MockScriptedProvider:
    name = "mock_scripted"
    is_real_llm = False

    def generate(self, request: GenerationRequest, model: str) -> GenerationResult:
        case = request.case or {}
        meta: dict[str, Any] = case.get("metadata") or {}
        script = str(request.params.get("script", "default"))
        outputs = meta.get("scripted_outputs") or {}
        if script not in outputs:
            raise ProviderError(f"case has no scripted output for script '{script}'")
        value = outputs[script]
        text = value if isinstance(value, str) else json.dumps(value)
        return GenerationResult(
            text=text,
            provider=self.name,
            model=model,
            input_tokens=estimate_tokens(request.system_prompt + request.user_prompt),
            output_tokens=estimate_tokens(text),
            tokens_estimated=True,
            parsed=value if not isinstance(value, str) else try_parse_json(value),
            notes=f"scripted output '{script}' from dataset; not a model",
        )
