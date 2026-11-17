"""Google Gemini provider via google-genai. Untested against the live API (no key in dev)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.llm.base import (
    GenerationRequest,
    GenerationResult,
    ProviderError,
    ProviderNotConfigured,
    TransientProviderError,
    try_parse_json,
)


class GeminiProvider:
    name = "gemini"
    is_real_llm = True

    def __init__(self) -> None:
        key = get_settings().gemini_api_key
        if not key:
            raise ProviderNotConfigured("GEMINI_API_KEY is not set")
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise ProviderNotConfigured("google-genai not installed (uv sync --extra gemini)") from exc
        self._client = genai.Client(api_key=key)

    def generate(self, request: GenerationRequest, model: str) -> GenerationResult:
        from google.genai import types

        cfg: dict[str, Any] = {"system_instruction": request.system_prompt or None}
        if "temperature" in request.params:
            cfg["temperature"] = request.params["temperature"]
        if "max_output_tokens" in request.params:
            cfg["max_output_tokens"] = request.params["max_output_tokens"]
        if request.json_schema:
            cfg["response_mime_type"] = "application/json"
            cfg["response_json_schema"] = request.json_schema
        try:
            resp = self._client.models.generate_content(
                model=model, contents=request.user_prompt, config=types.GenerateContentConfig(**cfg)
            )
        except Exception as exc:  # SDK raises various error types; classify by message
            msg = str(exc)
            if any(code in msg for code in ("429", "500", "502", "503", "504", "timeout", "Timeout")):
                raise TransientProviderError(msg[:500]) from exc
            raise ProviderError(msg[:500]) from exc
        text = resp.text or ""
        usage = resp.usage_metadata
        return GenerationResult(
            text=text,
            provider=self.name,
            model=model,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            parsed=try_parse_json(text) if request.json_schema else None,
        )
