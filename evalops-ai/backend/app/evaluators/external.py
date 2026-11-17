"""Optional adapters for DeepEval / RAGAS (evaluator types "deepeval" / "ragas").

These libraries are NOT dependencies of the core platform. The adapter is enabled only when the
package is importable AND a real LLM provider key is configured; otherwise the metric is recorded
as skipped with the reason. Scores from these libraries are LLM-based -> is_estimate=True.
See docs/evaluation-methodology.md for the current implementation status.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from app.core.config import get_settings
from app.evaluators.base import CaseData, EvalOutcome, TargetOutput


def _availability(package: str, openai_only: bool = False) -> str | None:
    """Return a skip reason, or None if the adapter may run."""
    if importlib.util.find_spec(package) is None:
        return f"skipped: optional package '{package}' is not installed"
    s = get_settings()
    if openai_only and not s.openai_api_key:
        return f"skipped: {package} adapter requires OPENAI_API_KEY"
    if not (s.openai_api_key or s.gemini_api_key):
        return f"skipped: {package} metrics require a configured LLM provider key"
    return None


def deepeval_metric(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    metric = f"deepeval_{params.get('metric', 'answer_relevancy')}"
    reason = _availability("deepeval")
    if reason:
        return EvalOutcome.skipped(metric, reason, is_estimate=True)
    from app.evaluators import _deepeval_impl  # type: ignore[attr-defined]

    return _deepeval_impl.run(case, out, params, threshold, metric)


def ragas_metric(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    metric = f"ragas_{params.get('metric', 'faithfulness')}"
    reason = _availability("ragas", openai_only=True)
    if reason:
        return EvalOutcome.skipped(metric, reason, is_estimate=True)
    from app.evaluators import _ragas_impl  # type: ignore[attr-defined]

    return _ragas_impl.run(case, out, params, threshold, metric)
