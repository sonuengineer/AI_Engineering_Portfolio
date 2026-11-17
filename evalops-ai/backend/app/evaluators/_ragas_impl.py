"""RAGAS adapter body (imported only when ragas is installed and an OpenAI key is configured).

API verified by introspection against ragas==0.4.4:
  ragas.llms.llm_factory(model, provider="openai", client=openai.OpenAI(...))
  ragas.metrics.collections.Faithfulness(llm=).score(user_input=, response=, retrieved_contexts=) -> MetricResult(.value)
  ragas.metrics.collections.ContextRecall(llm=).score(user_input=, retrieved_contexts=, reference=)
Only the OpenAI client path is wired. Not exercised against a live provider.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.evaluators.base import CaseData, EvalOutcome, TargetOutput


def run(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None, metric: str) -> EvalOutcome:
    s = get_settings()
    if not s.openai_api_key:
        return EvalOutcome.skipped(metric, "skipped: ragas adapter currently supports the OpenAI client only",
                                   is_estimate=True)
    from openai import OpenAI
    from ragas.llms import llm_factory
    from ragas.metrics.collections import ContextRecall, Faithfulness

    llm = llm_factory(s.openai_model, provider="openai", client=OpenAI(api_key=s.openai_api_key))
    name = str(params.get("metric", "faithfulness"))
    contexts = out.contexts or case.reference_contexts
    if name == "faithfulness":
        res = Faithfulness(llm=llm).score(user_input=case.input, response=out.text, retrieved_contexts=contexts)
    elif name == "context_recall":
        if not case.expected_output:
            return EvalOutcome.skipped(metric, "context_recall needs expected_output", is_estimate=True)
        res = ContextRecall(llm=llm).score(user_input=case.input, retrieved_contexts=contexts,
                                           reference=case.expected_output)
    else:
        return EvalOutcome.skipped(metric, f"ragas metric '{name}' not supported by this adapter", is_estimate=True)
    value = float(res.value) if res.value is not None else None
    thr = threshold if threshold is not None else 0.7
    return EvalOutcome(metric, value=value, passed=(value >= thr) if value is not None else None, is_estimate=True,
                       explanation=str(getattr(res, "reason", "") or "")[:2000],
                       details={"library": "ragas", "metric": name})
