"""OpenAI provider via chat completions. Untested against the live API (no key in dev)."""

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


class OpenAIProvider:
    name = "openai"
    is_real_llm = True

    def __init__(self) -> None:
        key = get_settings().openai_api_key
        if not key:
            raise ProviderNotConfigured("OPENAI_API_KEY is not set")
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise ProviderNotConfigured("openai not installed (uv sync --extra openai)") from exc
        self._openai = openai
        self._client = openai.OpenAI(api_key=key)

    def generate(self, request: GenerationRequest, model: str) -> GenerationResult:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "timeout": request.timeout_s}
        for k in ("temperature", "seed", "max_completion_tokens"):
            if k in request.params:
                kwargs[k] = request.params[k]
        if request.json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": request.json_schema, "strict": False},
            }
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except (self._openai.APITimeoutError, self._openai.RateLimitError, self._openai.APIConnectionError) as exc:
            raise TransientProviderError(str(exc)[:500]) from exc
        except self._openai.APIStatusError as exc:
            status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", 0)
            if int(status or 0) >= 500:
                raise TransientProviderError(str(exc)[:500]) from exc
            raise ProviderError(str(exc)[:500]) from exc
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return GenerationResult(
            text=text,
            provider=self.name,
            model=model,
            input_tokens=int(usage.prompt_tokens) if usage else 0,
            output_tokens=int(usage.completion_tokens) if usage else 0,
            parsed=try_parse_json(text) if request.json_schema else None,
        )
