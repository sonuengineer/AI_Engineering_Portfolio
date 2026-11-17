"""OpenAI planner via chat completions + JSON schema response format. Untested against the live API."""

from __future__ import annotations

from datetime import date

from app.llm.base import PlannerProvider, ProviderError, Usage
from app.llm.structured import estimate_cost, outcome_schema, run_with_repair, system_prompt
from app.schemas.plan import PlannerOutcome


class OpenAIPlanner(PlannerProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, as_of: date, max_rows: int) -> None:
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is not set")
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=30)
        self.model = model
        self._system = system_prompt(as_of, max_rows)

    def plan(self, question: str) -> tuple[PlannerOutcome, Usage]:
        def call(message: str) -> tuple[str, Usage]:
            try:
                resp = self._client.chat.completions.create(
                    model=str(self.model),
                    temperature=0,
                    messages=[
                        {"role": "system", "content": self._system},
                        {"role": "user", "content": message},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {"name": "planner_outcome", "schema": outcome_schema(), "strict": False},
                    },
                )
            except Exception as e:
                raise ProviderError(f"openai call failed: {type(e).__name__}") from e
            u = resp.usage
            usage = Usage(input_tokens=u.prompt_tokens if u else 0, output_tokens=u.completion_tokens if u else 0)
            return resp.choices[0].message.content or "", usage

        outcome, usage = run_with_repair(call, question)
        usage.estimated_cost_usd = estimate_cost(str(self.model), usage)
        return outcome, usage
