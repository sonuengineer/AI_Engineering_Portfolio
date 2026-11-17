"""Gemini planner via google-genai. Untested against the live API (no key available in dev)."""

from __future__ import annotations

from datetime import date

from app.llm.base import PlannerProvider, ProviderError, Usage
from app.llm.structured import estimate_cost, outcome_schema, run_with_repair, system_prompt
from app.schemas.plan import PlannerOutcome


class GeminiPlanner(PlannerProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, as_of: date, max_rows: int) -> None:
        if not api_key:
            raise ProviderError("GEMINI_API_KEY is not set")
        from google import genai  # imported lazily: optional at runtime

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self._system = system_prompt(as_of, max_rows)

    def plan(self, question: str) -> tuple[PlannerOutcome, Usage]:
        from google.genai import types

        def call(message: str) -> tuple[str, Usage]:
            try:
                resp = self._client.models.generate_content(
                    model=str(self.model),
                    contents=message,
                    config=types.GenerateContentConfig(
                        system_instruction=self._system,
                        response_mime_type="application/json",
                        response_json_schema=outcome_schema(),
                        temperature=0,
                    ),
                )
            except Exception as e:  # SDK raises several error types
                raise ProviderError(f"gemini call failed: {type(e).__name__}") from e
            meta = resp.usage_metadata
            usage = Usage(
                input_tokens=(meta.prompt_token_count or 0) if meta else 0,
                output_tokens=(meta.candidates_token_count or 0) if meta else 0,
            )
            return resp.text or "", usage

        outcome, usage = run_with_repair(call, question)
        usage.estimated_cost_usd = estimate_cost(str(self.model), usage)
        return outcome, usage
