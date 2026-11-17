"""DeepEval adapter body (imported only when deepeval is installed and a key is configured).

API verified by introspection against deepeval==4.3.4:
  LLMTestCase(input=, actual_output=, expected_output=, retrieval_context=)
  AnswerRelevancyMetric / FaithfulnessMetric(threshold=, model=, async_mode=) ; .measure(tc) ; .score ; .reason
  OpenAIModel(model=, api_key=) ; GeminiModel(model=, api_key=)
Not exercised against a live provider (no keys in the build environment).
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.evaluators.base import CaseData, EvalOutcome, TargetOutput


def _model() -> Any:
    s = get_settings()
    if s.openai_api_key:
        from deepeval.models import OpenAIModel

        return OpenAIModel(model=s.openai_model, api_key=s.openai_api_key)
    from deepeval.models import GeminiModel

    return GeminiModel(model=s.gemini_model, api_key=s.gemini_api_key)


def run(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None, metric: str) -> EvalOutcome:
    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
    from deepeval.test_case import LLMTestCase

    name = str(params.get("metric", "answer_relevancy"))
    classes = {"answer_relevancy": AnswerRelevancyMetric, "faithfulness": FaithfulnessMetric}
    if name not in classes:
        return EvalOutcome.skipped(metric, f"deepeval metric '{name}' not supported by this adapter", is_estimate=True)
    contexts = out.contexts or case.reference_contexts
    tc = LLMTestCase(input=case.input, actual_output=out.text, expected_output=case.expected_output,
                     retrieval_context=contexts or None)
    m = classes[name](threshold=threshold if threshold is not None else 0.5, model=_model(), async_mode=False)
    m.measure(tc)
    score = float(m.score) if m.score is not None else None
    return EvalOutcome(metric, value=score, passed=bool(m.success) if score is not None else None, is_estimate=True,
                       explanation=str(m.reason or "")[:2000], details={"library": "deepeval", "metric": name})
