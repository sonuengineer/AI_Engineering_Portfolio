"""Gemini and OpenAI structured-output providers (require API keys; not exercised in CI)."""

from __future__ import annotations

import json
import time

from pydantic import ValidationError

from app.llm.base import LLMRequest, StructuredOutputError, T, Usage, estimate_cost


def _parse(schema: type[T], text: str) -> T:
    return schema.model_validate_json(text)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model_fast: str, model_strong: str):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._models = {"fast": model_fast, "strong": model_strong}

    def generate(self, request: LLMRequest, schema: type[T]) -> tuple[T, Usage]:
        from google.genai import types

        model = self._models[request.tier]
        user = request.user
        last_err: Exception | None = None
        for _attempt in range(2):  # one repair retry on invalid structured output
            t0 = time.perf_counter()
            resp = self._client.models.generate_content(
                model=model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=request.system,
                    response_mime_type="application/json",
                    response_json_schema=schema.model_json_schema(),
                    temperature=0.2,
                ),
            )
            latency = int((time.perf_counter() - t0) * 1000)
            meta = resp.usage_metadata
            tin = (meta.prompt_token_count or 0) if meta else 0
            tout = (meta.candidates_token_count or 0) if meta else 0
            usage = Usage("gemini", model, tin, tout, estimate_cost(model, tin, tout), latency)
            try:
                return _parse(schema, resp.text or ""), usage
            except ValidationError as exc:
                last_err = exc
                user = (
                    f"{request.user}\n\nYour previous reply did not match the JSON schema: "
                    f"{str(exc)[:500]}. Reply again with valid JSON only."
                )
        raise StructuredOutputError(f"gemini returned invalid structured output: {last_err}")


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model_fast: str, model_strong: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._models = {"fast": model_fast, "strong": model_strong}

    def generate(self, request: LLMRequest, schema: type[T]) -> tuple[T, Usage]:
        model = self._models[request.tier]
        messages = [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.user},
        ]
        last_err: Exception | None = None
        for _attempt in range(2):
            t0 = time.perf_counter()
            resp = self._client.chat.completions.create(  # type: ignore[call-overload]
                model=model,
                messages=messages,
                temperature=0.2,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
                },
            )
            latency = int((time.perf_counter() - t0) * 1000)
            tin = resp.usage.prompt_tokens if resp.usage else 0
            tout = resp.usage.completion_tokens if resp.usage else 0
            usage = Usage("openai", model, tin, tout, estimate_cost(model, tin, tout), latency)
            content = resp.choices[0].message.content or ""
            try:
                return _parse(schema, content), usage
            except (ValidationError, json.JSONDecodeError) as exc:
                last_err = exc
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Invalid JSON for schema: {str(exc)[:500]}. Retry."})
        raise StructuredOutputError(f"openai returned invalid structured output: {last_err}")
