"""LLM-as-judge: must refuse with deterministic providers; parse structured output from a real one.
The provider is mocked only at the SDK boundary (get_provider)."""

from app.evaluators import run_evaluator
from app.evaluators.base import CaseData, TargetOutput
from app.evaluators.judge import SKIP_REASON
from app.llm.base import GenerationResult


def _case():
    return CaseData(external_id="c", input="What is 2+2?", expected_output="4")


def test_judge_refuses_with_local_provider():
    r = run_evaluator("llm_judge", _case(), TargetOutput(text="4"), {}, 4.0)
    assert r.status == "skipped" and r.explanation == SKIP_REASON and r.is_estimate and r.value is None


def test_judge_refuses_when_real_provider_has_no_key():
    r = run_evaluator("llm_judge", _case(), TargetOutput(text="4"), {"provider": "openai"}, 4.0)
    assert r.status == "skipped" and r.explanation.startswith(SKIP_REASON) and r.is_estimate


class _FakeProvider:
    name = "openai"
    is_real_llm = True

    def __init__(self, parsed):
        self.parsed = parsed

    def generate(self, request, model):
        assert request.json_schema["required"] == ["score", "reasoning"]
        return GenerationResult(text="{}", provider="openai", model=model, parsed=self.parsed)


def test_judge_scores_are_estimates(monkeypatch):
    import app.evaluators.judge as judge

    monkeypatch.setattr(judge, "get_provider", lambda name: _FakeProvider({"score": 5, "reasoning": "correct"}))
    r = run_evaluator("llm_judge", _case(), TargetOutput(text="4"), {"provider": "openai"}, 4.0)
    assert r.status == "scored" and r.value == 5.0 and r.passed and r.is_estimate


def test_judge_invalid_output_is_error_not_score(monkeypatch):
    import app.evaluators.judge as judge

    monkeypatch.setattr(judge, "get_provider", lambda name: _FakeProvider({"score": 9}))
    r = run_evaluator("llm_judge", _case(), TargetOutput(text="4"), {"provider": "openai"}, 4.0)
    assert r.status == "error" and r.value is None


def test_optional_adapters_skip_without_package_or_key():
    for t in ("deepeval", "ragas"):
        r = run_evaluator(t, _case(), TargetOutput(text="4"), {}, None)
        assert r.status == "skipped" and r.is_estimate
