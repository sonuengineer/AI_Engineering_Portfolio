import pytest

from app.evaluators import REGISTRY, run_evaluator
from app.evaluators.base import CaseData, TargetOutput
from app.evaluators.deterministic import normalize_text


def case(**kw):
    base = {"external_id": "c1", "input": "q?"}
    base.update(kw)
    return CaseData(**base)


def ev(type_, c, o, params=None, threshold=None):
    return run_evaluator(type_, c, o, params or {}, threshold)


def test_registry_kinds():
    assert REGISTRY["exact_match"].kind == "deterministic"
    assert REGISTRY["llm_judge"].kind == "judge"
    assert {"sql_result_match", "status_match", "citation_correctness", "groundedness_lexical"} <= set(REGISTRY)


def test_exact_and_normalized_match():
    c = case(expected_output="The answer is 42.")
    assert ev("exact_match", c, TargetOutput(text=" The answer is 42. ")).passed
    assert not ev("exact_match", c, TargetOutput(text="the answer is 42")).passed
    assert ev("normalized_match", c, TargetOutput(text="answer is 42")).passed
    assert normalize_text("The  Cat, an Animal!") == "cat animal"
    r = ev("normalized_match", c, TargetOutput(text="Well, the answer is 42. Thanks"), {"allow_containment": True})
    assert r.passed


def test_skipped_when_no_expectation():
    r = ev("exact_match", case(), TargetOutput(text="x"))
    assert r.status == "skipped" and r.passed is None


def test_contains_all_any_and_threshold():
    c = case(metadata={"expected_keywords": ["SAML", "OpenID"]})
    r = ev("contains", c, TargetOutput(text="supports saml only"))
    assert r.value == 0.5 and not r.passed and r.details["missing"] == ["OpenID"]
    assert ev("contains", c, TargetOutput(text="saml"), {"mode": "any"}).passed
    assert ev("contains", c, TargetOutput(text="saml"), {}, 0.5).passed


def test_not_contains_and_regex():
    c = case(metadata={"must_not_contain": ["41 percent"], "expected_regex": r"not (available|found)"})
    assert ev("not_contains", c, TargetOutput(text="This is not available.")).passed
    assert not ev("not_contains", c, TargetOutput(text="It is 41 percent")).passed
    assert ev("regex", c, TargetOutput(text="Info NOT FOUND")).passed
    assert ev("regex", case(), TargetOutput(text="x"), {"pattern": "("}).status == "error"


def test_json_schema_valid():
    schema = {"type": "object", "properties": {"total": {"type": "number"}}, "required": ["total"]}
    c = case(metadata={"json_schema": schema})
    assert ev("json_schema_valid", c, TargetOutput(text='{"total": 3.5}')).passed
    bad = ev("json_schema_valid", c, TargetOutput(text='{"total": "x"}'))
    assert not bad.passed and "number" in bad.explanation
    assert ev("json_schema_valid", c, TargetOutput(text="not json")).explanation == "output is not valid JSON"


def test_numeric_tolerance_text_and_json_field():
    c = case(expected_output="1,250.00")
    assert ev("numeric_tolerance", c, TargetOutput(text="Total: 1250"), {"rel_tol": 0.0, "abs_tol": 0.001}).passed
    assert not ev("numeric_tolerance", c, TargetOutput(text="Total: 1300"), {"rel_tol": 0.01}).passed
    c2 = case(metadata={"expected_number": 99.99})
    out = TargetOutput(text='{"invoice_number": "INV-3344", "total": 99.99}')
    assert ev("numeric_tolerance", c2, out, {"json_field": "total"}).passed
    # without json_field the first number (3344) is used -> fails, documenting why json_field exists
    assert not ev("numeric_tolerance", c2, out).passed


def test_citation_precision_recall():
    c = case(expected_citations=["d1", "d2"])
    r = ev("citation_correctness", c, TargetOutput(citations=["d1", "d3"]))
    assert r.value == 0.5 and r.details["precision"] == 0.5 and not r.passed
    r2 = ev("citation_correctness", c, TargetOutput(citations=["d1", "d2", "d9"]))
    assert r2.passed and r2.details["recall"] == 1.0 and r2.details["precision"] == pytest.approx(2 / 3)
    assert ev("citation_correctness", c, TargetOutput(citations=[])).value == 0.0


def test_context_precision_recall_lexical():
    refs = ["Payment is due within 30 days of the invoice date."]
    c = case(reference_contexts=refs)
    good = TargetOutput(contexts=["Payment is due within 30 days of the invoice date. Late fees apply.",
                                  "Our office dog is named Rex."])
    p = ev("context_precision_lexical", c, good)
    assert p.value == 0.5 and "lexical" in p.explanation
    assert ev("context_recall_lexical", c, good).value == 1.0
    assert ev("context_recall_lexical", c, TargetOutput(contexts=["unrelated text about dogs"])).value == 0.0
    assert not ev("context_precision_lexical", c, TargetOutput()).passed


def test_groundedness_lexical():
    ctx = ["Encryption keys are rotated every 90 days."]
    c = case(reference_contexts=ctx)
    grounded = ev("groundedness_lexical", c, TargetOutput(text="Yes. Encryption keys are rotated every 90 days.",
                                                          contexts=ctx))
    assert grounded.value == 1.0 and grounded.passed  # "Yes." too short to check
    halluc = ev("groundedness_lexical", c, TargetOutput(
        text="Keys are rotated every 90 days. The CEO personally approves each customer contract renewal.",
        contexts=ctx))
    assert halluc.value == 0.5 and not halluc.passed
    assert halluc.details["unsupported_sentences"]


def test_sql_result_match():
    c = case(metadata={"expected_rows": [["North", 10.5], ["South", "20.25"]]})
    assert ev("sql_result_match", c, TargetOutput(rows=[["south", 20.25], ["North", "10.50"]])).passed
    partial = ev("sql_result_match", c, TargetOutput(rows=[["North", 10.5], ["South", 99]]))
    assert not partial.passed and partial.value == 0.5
    assert not ev("sql_result_match", c, TargetOutput(rows=[["South", 20.25], ["North", 10.5]]),
                  {"order_sensitive": True}).passed
    assert not ev("sql_result_match", c, TargetOutput(rows=None)).passed


def test_status_latency_cost():
    c = case(metadata={"expected_status": "rejected"})
    assert ev("status_match", c, TargetOutput(status="rejected")).passed
    assert not ev("status_match", c, TargetOutput(status="answered")).passed
    assert ev("latency_threshold", case(), TargetOutput(latency_ms=120), {"max_ms": 200}).passed
    assert not ev("latency_threshold", case(), TargetOutput(latency_ms=250), {"max_ms": 200}).passed
    assert ev("cost_threshold", case(), TargetOutput(cost_usd=0.001), {"max_usd": 0.01}).passed
    assert not ev("cost_threshold", case(), TargetOutput(cost_usd=0.02), {"max_usd": 0.01}).passed


def test_unknown_type_and_evaluator_crash_are_captured(monkeypatch):
    assert ev("nope", case(), TargetOutput()).status == "error"
    import app.evaluators as evs

    def boom(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setitem(evs.REGISTRY, "exact_match", evs.EvaluatorSpec("exact_match", "deterministic", boom, ""))
    r = ev("exact_match", case(expected_output="x"), TargetOutput(text="x"))
    assert r.status == "error" and "RuntimeError" in r.explanation


def test_groundedness_skips_expected_abstentions():
    """Regression: correct refusals were scored as ungrounded (found in the live NEXUS benchmark)."""
    ctx = ["Standard payment terms are net 45 days from invoice date."]
    refusal_re = "could not find|not enough evidence"
    unanswerable = case(tags=["unanswerable"], metadata={"expected_regex": refusal_re})
    refusal = TargetOutput(text="I could not find enough evidence in the indexed documents to answer this.", contexts=ctx)
    out = ev("groundedness_lexical", unanswerable, refusal)
    assert out.status == "skipped" and out.passed is None and "abstention" in out.explanation
    # A hallucinated answer to an unanswerable question is NOT skipped: it is still scored (and fails).
    halluc = TargetOutput(text="Globex targets a 41 percent margin on all electrical products this year.", contexts=ctx)
    assert ev("groundedness_lexical", unanswerable, halluc).passed is False
    # Without the tag a refusal is scored normally: the skip is driven by the case expectation.
    assert ev("groundedness_lexical", case(), refusal).passed is False
    # Tags are configurable.
    assert ev("groundedness_lexical", case(tags=["refuse"]), refusal, {"skip_tags": ["refuse"]}).status == "skipped"
