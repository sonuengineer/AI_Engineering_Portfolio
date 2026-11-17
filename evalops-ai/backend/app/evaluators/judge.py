"""LLM-as-judge evaluator.

Requires a real configured LLM provider (gemini/openai with a key). With `local` or
`mock_scripted` it refuses and records status=skipped -- it never fabricates a score.
All judge scores are is_estimate=True.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.evaluators.base import CaseData, EvalOutcome, TargetOutput
from app.llm import get_provider
from app.llm.base import GenerationRequest, ProviderError

SKIP_REASON = "skipped: judge requires a configured LLM provider"

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 5},
        "reasoning": {"type": "string"},
    },
    "required": ["score", "reasoning"],
}

DEFAULT_CRITERIA = "correctness and completeness of the answer with respect to the question and reference"

SYSTEM = (
    "You are a strict evaluation judge. Score the candidate answer from 1 (very poor) to 5 (excellent) "
    "against the rubric. Respond only with JSON matching the schema: {\"score\": int, \"reasoning\": str}."
)


def build_judge_prompt(case: CaseData, out: TargetOutput, criteria: str, rubric: str | None) -> str:
    parts = [f"Criteria: {criteria}"]
    if rubric:
        parts.append(f"Rubric:\n{rubric}")
    parts.append(f"Question:\n{case.input}")
    if case.expected_output:
        parts.append(f"Reference answer:\n{case.expected_output}")
    if out.contexts:
        parts.append("Retrieved context:\n" + "\n---\n".join(out.contexts[:5]))
    parts.append(f"Candidate answer:\n{out.text}")
    return "\n\n".join(parts)


def llm_judge(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    metric = str(params.get("metric_name", "llm_judge"))
    provider_name = str(params.get("provider") or get_settings().llm_provider)
    if provider_name in ("local", "mock_scripted"):
        return EvalOutcome.skipped(metric, SKIP_REASON, is_estimate=True)
    try:
        provider = get_provider(provider_name)
    except ProviderError as exc:
        return EvalOutcome.skipped(metric, f"{SKIP_REASON} ({exc})", is_estimate=True)
    s = get_settings()
    model = str(params.get("model") or (s.gemini_model if provider_name == "gemini" else s.openai_model))
    req = GenerationRequest(
        system_prompt=SYSTEM,
        user_prompt=build_judge_prompt(case, out, str(params.get("criteria", DEFAULT_CRITERIA)), params.get("rubric")),
        params={"temperature": 0},
        json_schema=JUDGE_SCHEMA,
    )
    try:
        res = provider.generate(req, model)
    except ProviderError as exc:
        return EvalOutcome(metric, status="error", is_estimate=True, explanation=f"judge call failed: {exc}"[:500])
    parsed = res.parsed if isinstance(res.parsed, dict) else None
    if not parsed or not isinstance(parsed.get("score"), int) or not 1 <= parsed["score"] <= 5:
        return EvalOutcome(metric, status="error", is_estimate=True, explanation="judge returned invalid structured output")
    score = float(parsed["score"])
    passed = score >= (threshold if threshold is not None else 4.0)
    return EvalOutcome(metric, value=score, passed=passed, is_estimate=True,
                       explanation=str(parsed.get("reasoning", ""))[:2000],
                       details={"judge_provider": provider_name, "judge_model": model,
                                "judge_input_tokens": res.input_tokens, "judge_output_tokens": res.output_tokens})
