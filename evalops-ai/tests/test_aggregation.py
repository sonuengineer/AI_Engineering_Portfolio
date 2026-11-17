import pytest

from app.services.aggregation import ResultRow, ScoreRow, case_passed, percentile, summarize
from app.services.comparison import compare_summaries, diff_cases
from app.services.gate import check_thresholds


def test_percentile_linear():
    assert percentile([], 50) is None
    assert percentile([5], 95) == 5
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile(list(range(1, 101)), 95) == pytest.approx(95.05)


def test_case_passed_ignores_estimates_and_skips():
    s = [ScoreRow("c", "m1", "scored", 1, True, False), ScoreRow("c", "judge", "scored", 1, False, True),
         ScoreRow("c", "m2", "skipped", None, None, False)]
    assert case_passed(s, None) is True
    assert case_passed(s, "boom") is False
    assert case_passed([ScoreRow("c", "j", "skipped", None, None, True)], None) is None
    assert case_passed([ScoreRow("c", "m", "scored", 0, False, False, gating=False)], None) is None


def test_summarize():
    results = [ResultRow("a", 10, 5, 7, 0.001, None, True), ResultRow("b", 30, 5, 3, 0.002, None, False),
               ResultRow("c", None, 0, 0, 0.0, "timeout", False)]
    scores = [ScoreRow("a", "m", "scored", 1, True, False), ScoreRow("b", "m", "scored", 0, False, False),
              ScoreRow("a", "judge", "skipped", None, None, True)]
    s = summarize(results, scores, wall_seconds=2.0)
    assert s["case_count"] == 3 and s["error_count"] == 1 and s["error_rate"] == pytest.approx(1 / 3)
    assert s["latency_ms"]["mean"] == 20 and s["latency_ms"]["p50"] == 20
    assert s["tokens"] == {"input": 10, "output": 10, "total": 20}
    assert s["cost_usd"] == pytest.approx(0.003)
    assert s["throughput_cases_per_sec"] == 1.5
    assert s["metrics"]["m"]["pass_rate"] == 0.5 and s["metrics"]["m"]["mean"] == 0.5
    assert s["metrics"]["judge"]["skipped"] == 1 and s["metrics"]["judge"]["pass_rate"] is None
    assert s["metrics"]["judge"]["is_estimate"] is True
    assert s["overall_pass_rate"] == pytest.approx(1 / 3)


def _summ(m_rate, judge_rate=None, p95=10.0, err=0.0, overall=None):
    metrics = {"m": {"pass_rate": m_rate, "is_estimate": False}}
    if judge_rate is not None:
        metrics["judge"] = {"pass_rate": judge_rate, "is_estimate": True}
    return {"metrics": metrics, "latency_ms": {"p95": p95}, "error_rate": err, "cost_usd": 0.0,
            "overall_pass_rate": overall if overall is not None else m_rate}


def test_regression_detection_with_tolerance():
    r = compare_summaries(_summ(0.90), _summ(0.89), tolerance=0.02)
    assert not r["has_regression"]
    r = compare_summaries(_summ(0.90), _summ(0.80), tolerance=0.02)
    assert r["has_regression"] and "m" in r["regressions"]
    r = compare_summaries(_summ(0.90), _summ(0.80), tolerance=0.02, metric_tolerances={"m": 0.2})
    assert "m" not in r["regressions"]


def test_judge_drop_is_reported_but_not_a_regression():
    r = compare_summaries(_summ(0.9, judge_rate=0.9), _summ(0.9, judge_rate=0.1))
    row = next(x for x in r["metrics"] if x["metric"] == "judge")
    assert row["regression"] and row["is_estimate"]
    assert not r["has_regression"]


def test_latency_and_error_rate_regressions():
    r = compare_summaries(_summ(1.0, p95=100), _summ(1.0, p95=200), latency_tolerance_pct=0.25)
    assert "latency_p95_ms" in r["regressions"]
    r = compare_summaries(_summ(1.0, err=0.0), _summ(1.0, err=0.1))
    assert "error_rate" in r["regressions"]


def test_diff_cases():
    d = diff_cases({"a": True, "b": False, "c": True, "x": True}, {"a": False, "b": True, "c": True, "y": False})
    assert d["newly_failing"] == ["a"] and d["newly_passing"] == ["b"]
    assert d["only_in_baseline"] == ["x"] and d["only_in_candidate"] == ["y"]


def test_check_thresholds():
    s = {"metrics": {"m": {"pass_rate": 0.8}}, "overall_pass_rate": 0.8, "error_rate": 0.1,
         "latency_ms": {"p95": 500}, "cost_usd": 0.5, "case_count": 3}
    f = check_thresholds(s, {"min_pass_rate": {"m": 0.9, "missing": 0.5}, "min_overall_pass_rate": 0.9,
                             "max_error_rate": 0.0, "max_p95_latency_ms": 100, "max_cost_usd": 0.1, "min_cases": 5})
    assert len(f) == 7
    assert check_thresholds(s, {"min_pass_rate": {"m": 0.8}}) == []
