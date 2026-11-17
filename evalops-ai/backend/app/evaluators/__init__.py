"""Evaluator registry: type -> (kind, function, description)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.evaluators.base import CaseData, EvalOutcome, TargetOutput
from app.evaluators.deterministic import DETERMINISTIC, EvalFn
from app.evaluators.external import deepeval_metric, ragas_metric
from app.evaluators.judge import llm_judge


@dataclass(frozen=True)
class EvaluatorSpec:
    type: str
    kind: str  # deterministic | judge
    fn: EvalFn
    description: str


_DESCRIPTIONS = {
    "exact_match": "Output equals expected_output exactly (trimmed).",
    "normalized_match": "Equality after lowercasing and stripping punctuation/articles/whitespace.",
    "contains": "Expected substrings (params.substrings or metadata.expected_keywords) present.",
    "not_contains": "None of the forbidden substrings (params.substrings or metadata.must_not_contain) appear.",
    "regex": "Output matches params.pattern or metadata.expected_regex.",
    "json_schema_valid": "Output parses as JSON and validates against a JSON Schema.",
    "numeric_tolerance": "First number in output within rel/abs tolerance of the expected number.",
    "citation_correctness": "Recall/precision of returned document ids vs expected_citations.",
    "context_precision_lexical": "Lexical heuristic: share of retrieved contexts overlapping a reference context.",
    "context_recall_lexical": "Lexical heuristic: share of reference contexts covered by retrieved contexts.",
    "groundedness_lexical": "Lexical heuristic: share of answer sentences with token support in contexts.",
    "sql_result_match": "Returned rows equal metadata.expected_rows (multiset, rounded).",
    "status_match": "Target status equals metadata.expected_status.",
    "latency_threshold": "Per-case latency under params.max_ms.",
    "cost_threshold": "Per-case estimated cost under params.max_usd.",
}

REGISTRY: dict[str, EvaluatorSpec] = {
    name: EvaluatorSpec(name, "deterministic", fn, _DESCRIPTIONS[name]) for name, fn in DETERMINISTIC.items()
}
REGISTRY["llm_judge"] = EvaluatorSpec(
    "llm_judge", "judge", llm_judge, "LLM-as-judge 1-5 rubric score (estimate; needs a real provider)."
)
REGISTRY["deepeval"] = EvaluatorSpec(
    "deepeval", "judge", deepeval_metric, "Optional DeepEval adapter (estimate; needs package + provider key)."
)
REGISTRY["ragas"] = EvaluatorSpec(
    "ragas", "judge", ragas_metric, "Optional RAGAS adapter (estimate; needs package + provider key)."
)


def run_evaluator(
    type_: str, case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None
) -> EvalOutcome:
    spec = REGISTRY.get(type_)
    if spec is None:
        return EvalOutcome(type_, status="error", explanation=f"unknown evaluator type '{type_}'")
    try:
        outcome = spec.fn(case, out, params, threshold)
    except Exception as exc:  # evaluator bugs must not kill the run
        return EvalOutcome(type_, status="error", explanation=f"evaluator raised {type(exc).__name__}: {exc}"[:500],
                           is_estimate=spec.kind == "judge")
    if spec.kind == "judge":
        outcome.is_estimate = True
    return outcome


__all__ = ["REGISTRY", "CaseData", "EvalOutcome", "EvaluatorSpec", "TargetOutput", "run_evaluator"]
