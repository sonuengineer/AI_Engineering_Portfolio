"""Deterministic evaluators. Pure functions, no network, fully unit tested.

Lexical metrics (context_precision_lexical, context_recall_lexical, groundedness_lexical) are
heuristics based on token overlap. They are labeled as such and are NOT semantic judgments.
"""

from __future__ import annotations

import json
import math
import re
import string
from collections import Counter
from collections.abc import Callable
from typing import Any

import jsonschema

from app.evaluators.base import CaseData, EvalOutcome, TargetOutput

EvalFn = Callable[[CaseData, TargetOutput, dict[str, Any], float | None], EvalOutcome]

_WORD_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
STOPWORDS = frozenset(
    "a an the of to in on for and or but is are was were be been being it its this that these those with by at "
    "from as into about than then so such not no do does did has have had which who whom what when where why how "
    "our we you your they their them he she his her i me my can could would should will shall may might".split()
)


def tokenize(text: str, *, drop_stopwords: bool = True) -> list[str]:
    toks = _WORD_RE.findall((text or "").lower())
    return [t for t in toks if not (drop_stopwords and t in STOPWORDS)]


def normalize_text(text: str) -> str:
    t = (text or "").lower()
    t = t.translate(str.maketrans("", "", string.punctuation))
    t = re.sub(r"\b(a|an|the)\b", " ", t)
    return " ".join(t.split())


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def _pass(value: float, threshold: float | None, default: float) -> bool:
    return value >= (default if threshold is None else threshold)


def _expected(case: CaseData, params: dict[str, Any]) -> str | None:
    if "expected" in params:
        return str(params["expected"])
    return case.expected_output


# --------------------------------------------------------------------------- string matching


def exact_match(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    exp = _expected(case, params)
    if exp is None:
        return EvalOutcome.skipped("exact_match", "case has no expected_output")
    ok = out.text.strip() == exp.strip()
    return EvalOutcome("exact_match", value=1.0 if ok else 0.0, passed=ok,
                       explanation="exact string equality (whitespace-trimmed)")


def normalized_match(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    exp = _expected(case, params)
    if exp is None:
        return EvalOutcome.skipped("normalized_match", "case has no expected_output")
    a, b = normalize_text(out.text), normalize_text(exp)
    ok = a == b or (bool(params.get("allow_containment")) and bool(b) and b in a)
    return EvalOutcome("normalized_match", value=1.0 if ok else 0.0, passed=ok,
                       explanation="lowercase, strip punctuation/articles/whitespace, then compare")


def contains(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    needles = params.get("substrings") or case.metadata.get("expected_keywords") or []
    if not needles:
        return EvalOutcome.skipped("contains", "no substrings in params or metadata.expected_keywords")
    case_sensitive = bool(params.get("case_sensitive", False))
    hay = out.text if case_sensitive else out.text.lower()
    found = [n for n in needles if (n if case_sensitive else str(n).lower()) in hay]
    missing = [n for n in needles if n not in found]
    mode = params.get("mode", "all")
    value = len(found) / len(needles)
    passed = bool(found) if mode == "any" else _pass(value, threshold, 1.0)
    return EvalOutcome("contains", value=value, passed=passed,
                       explanation=f"{len(found)}/{len(needles)} expected substrings present (mode={mode})",
                       details={"found": found, "missing": missing})


def not_contains(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    banned = params.get("substrings") or case.metadata.get("must_not_contain") or []
    if not banned:
        return EvalOutcome.skipped("not_contains", "no forbidden substrings in params or metadata.must_not_contain")
    hay = out.text.lower()
    hits = [b for b in banned if str(b).lower() in hay]
    ok = not hits
    return EvalOutcome("not_contains", value=1.0 if ok else 0.0, passed=ok,
                       explanation="no forbidden substrings present" if ok else f"forbidden substrings present: {hits}",
                       details={"hits": hits})


def regex(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    pattern = params.get("pattern") or case.metadata.get("expected_regex")
    if not pattern:
        return EvalOutcome.skipped("regex", "no pattern in params or metadata.expected_regex")
    try:
        flags = re.IGNORECASE if params.get("ignore_case", True) else 0
        ok = re.search(pattern, out.text, flags) is not None
    except re.error as exc:
        return EvalOutcome("regex", status="error", explanation=f"invalid regex: {exc}")
    return EvalOutcome("regex", value=1.0 if ok else 0.0, passed=ok, explanation=f"re.search({pattern!r})")


def json_schema_valid(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    schema = params.get("schema") or case.metadata.get("json_schema")
    if not schema:
        return EvalOutcome.skipped("json_schema_valid", "no schema in params or metadata.json_schema")
    doc = out.json
    if doc is None:
        try:
            doc = json.loads(out.text)
        except (ValueError, TypeError):
            return EvalOutcome("json_schema_valid", value=0.0, passed=False, explanation="output is not valid JSON")
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    ok = not errors
    return EvalOutcome("json_schema_valid", value=1.0 if ok else 0.0, passed=ok,
                       explanation="valid against JSON Schema (draft 2020-12)" if ok else errors[0].message[:300],
                       details={"error_count": len(errors)})


def _parse_number(s: str) -> float | None:
    m = _NUM_RE.search(s or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def numeric_tolerance(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    exp_raw = params.get("expected", case.metadata.get("expected_number", case.expected_output))
    expected = _parse_number(str(exp_raw)) if exp_raw is not None else None
    if expected is None:
        return EvalOutcome.skipped("numeric_tolerance", "no numeric expected value")
    field = params.get("json_field")
    actual: float | None = None
    if field:
        doc = out.json if isinstance(out.json, dict) else None
        if doc is None:
            try:
                loaded = json.loads(out.text)
                doc = loaded if isinstance(loaded, dict) else None
            except (ValueError, TypeError):
                doc = None
        raw = doc.get(field) if doc else None
        actual = float(raw) if isinstance(raw, int | float) and not isinstance(raw, bool) else (
            _parse_number(str(raw)) if raw is not None else None)
    else:
        actual = _parse_number(out.text)
    if actual is None:
        return EvalOutcome("numeric_tolerance", value=0.0, passed=False, explanation="no number found in output")
    abs_tol = float(params.get("abs_tol", 0.0))
    rel_tol = float(params.get("rel_tol", 0.01))
    ok = math.isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol)
    return EvalOutcome("numeric_tolerance", value=1.0 if ok else 0.0, passed=ok,
                       explanation=f"actual={actual} expected={expected} rel_tol={rel_tol} abs_tol={abs_tol}",
                       details={"actual": actual, "expected": expected})


# --------------------------------------------------------------------------- RAG metrics


def citation_correctness(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    expected = {str(c) for c in case.expected_citations}
    if not expected:
        return EvalOutcome.skipped("citation_correctness", "case has no expected_citations")
    returned = {str(c) for c in out.citations}
    hit = expected & returned
    precision = len(hit) / len(returned) if returned else 0.0
    recall = len(hit) / len(expected)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    passed = _pass(recall, threshold, 1.0)
    return EvalOutcome("citation_correctness", value=recall, passed=passed,
                       explanation=f"citation recall={recall:.2f} precision={precision:.2f} f1={f1:.2f}",
                       details={"precision": precision, "recall": recall, "f1": f1,
                                "expected": sorted(expected), "returned": sorted(returned)})


def _overlap(a: list[str], b: set[str]) -> float:
    """Fraction of distinct tokens of a that appear in b."""
    sa = set(a)
    return len(sa & b) / len(sa) if sa else 0.0


def context_precision_lexical(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    if not case.reference_contexts:
        return EvalOutcome.skipped("context_precision_lexical", "case has no reference_contexts")
    if not out.contexts:
        return EvalOutcome("context_precision_lexical", value=0.0, passed=False,
                           explanation="target returned no retrieved contexts")
    tau = float(params.get("overlap", 0.5))
    refs = [set(tokenize(r)) for r in case.reference_contexts]
    relevant = 0
    for ctx in out.contexts:
        ct = tokenize(ctx)
        if any(_overlap(ct, r) >= tau or _overlap(list(r), set(ct)) >= tau for r in refs):
            relevant += 1
    value = relevant / len(out.contexts)
    return EvalOutcome("context_precision_lexical", value=value, passed=_pass(value, threshold, 0.5),
                       explanation=f"lexical heuristic: {relevant}/{len(out.contexts)} retrieved contexts overlap "
                                   f"(>= {tau}) with a reference context",
                       details={"method": "token_overlap", "overlap_threshold": tau})


def context_recall_lexical(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    if not case.reference_contexts:
        return EvalOutcome.skipped("context_recall_lexical", "case has no reference_contexts")
    tau = float(params.get("overlap", 0.5))
    retrieved = set(tokenize(" ".join(out.contexts)))
    covered = sum(1 for r in case.reference_contexts if _overlap(tokenize(r), retrieved) >= tau)
    value = covered / len(case.reference_contexts)
    return EvalOutcome("context_recall_lexical", value=value, passed=_pass(value, threshold, 1.0),
                       explanation=f"lexical heuristic: {covered}/{len(case.reference_contexts)} reference contexts "
                                   f"have >= {tau} token coverage in retrieved contexts",
                       details={"method": "token_overlap", "overlap_threshold": tau})


def groundedness_lexical(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    # A correct refusal ("I could not find enough evidence...") has no support in the contexts by
    # design, so scoring it would turn correct abstentions into failures. Skip (not pass) ONLY when
    # the case expects an abstention AND the output actually is one; a hallucinated answer to an
    # unanswerable question is still scored. Refusal correctness is judged by the refusal metric.
    skip_tags = set(params.get("skip_tags", ["unanswerable"]))
    hit = skip_tags.intersection(case.tags)
    if hit:
        pattern = params.get("abstention_pattern") or case.metadata.get("expected_regex")
        if pattern is None or re.search(str(pattern), out.text, re.IGNORECASE):
            reason = f"abstention expected (tag: {sorted(hit)[0]}) and output is a refusal; scored by refusal metric"
            return EvalOutcome.skipped("groundedness_lexical", reason)
    contexts = out.contexts or (case.reference_contexts if params.get("fallback_to_reference", True) else [])
    source = "retrieved" if out.contexts else "reference"
    if not contexts:
        return EvalOutcome.skipped("groundedness_lexical", "no contexts available")
    sentences = split_sentences(out.text)
    if not sentences:
        return EvalOutcome("groundedness_lexical", value=0.0, passed=False, explanation="empty answer")
    ctx_tokens = set(tokenize(" ".join(contexts)))
    tau = float(params.get("overlap", 0.6))
    min_tokens = int(params.get("min_tokens", 3))
    # Very short sentences ("Yes.", "No.") carry no checkable claim and are ignored.
    checked = [s for s in sentences if len(set(tokenize(s))) >= min_tokens]
    if not checked:
        return EvalOutcome("groundedness_lexical", value=1.0, passed=True,
                           explanation="no sentence long enough to check (all < min_tokens content tokens)",
                           details={"method": "token_overlap", "context_source": source, "checked": 0})
    supported = [s for s in checked if _overlap(tokenize(s), ctx_tokens) >= tau]
    unsupported = [s for s in checked if s not in supported]
    value = len(supported) / len(checked)
    return EvalOutcome("groundedness_lexical", value=value, passed=_pass(value, threshold, 0.8),
                       explanation=f"heuristic: {len(supported)}/{len(checked)} answer sentences have >= {tau} "
                                   f"token support in {source} contexts (not an entailment check)",
                       details={"method": "token_overlap", "context_source": source,
                                "unsupported_sentences": unsupported[:5]})


# --------------------------------------------------------------------------- DataWise metrics


def _norm_cell(v: Any, ndigits: int) -> Any:
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, int | float):
        return round(float(v), ndigits)
    if isinstance(v, str):
        try:
            return round(float(v.replace(",", "")), ndigits)
        except ValueError:
            return v.strip().lower()
    return json.dumps(v, sort_keys=True)


def sql_result_match(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    expected = case.metadata.get("expected_rows")
    if expected is None:
        return EvalOutcome.skipped("sql_result_match", "case has no metadata.expected_rows")
    if out.rows is None:
        return EvalOutcome("sql_result_match", value=0.0, passed=False, explanation="target returned no rows")
    nd = int(params.get("round_digits", 2))
    exp_rows = [tuple(_norm_cell(c, nd) for c in r) for r in expected]
    act_rows = [tuple(_norm_cell(c, nd) for c in r) for r in out.rows]
    if params.get("order_sensitive", False):
        ok = exp_rows == act_rows
    else:
        ok = Counter(exp_rows) == Counter(act_rows)
    overlap = sum((Counter(exp_rows) & Counter(act_rows)).values())
    denom = max(len(exp_rows), len(act_rows)) or 1
    return EvalOutcome("sql_result_match", value=1.0 if ok else overlap / denom, passed=ok,
                       explanation=f"rows match={ok} ({overlap}/{denom} rows in common, "
                                   f"order_sensitive={bool(params.get('order_sensitive', False))})",
                       details={"expected_count": len(exp_rows), "actual_count": len(act_rows)})


def status_match(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    expected = params.get("expected") or case.metadata.get("expected_status")
    if not expected:
        return EvalOutcome.skipped("status_match", "case has no metadata.expected_status")
    ok = (out.status or "") == expected
    return EvalOutcome("status_match", value=1.0 if ok else 0.0, passed=ok,
                       explanation=f"status={out.status!r} expected={expected!r}")


# --------------------------------------------------------------------------- operational


def latency_threshold(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    max_ms = float(params.get("max_ms", threshold if threshold is not None else 5000))
    if out.latency_ms is None:
        return EvalOutcome.skipped("latency_threshold", "no latency recorded")
    ok = out.latency_ms <= max_ms
    return EvalOutcome("latency_threshold", value=out.latency_ms, passed=ok,
                       explanation=f"latency {out.latency_ms:.1f} ms <= {max_ms:.0f} ms: {ok}")


def cost_threshold(case: CaseData, out: TargetOutput, params: dict[str, Any], threshold: float | None) -> EvalOutcome:
    max_usd = float(params.get("max_usd", threshold if threshold is not None else 0.01))
    ok = out.cost_usd <= max_usd
    return EvalOutcome("cost_threshold", value=out.cost_usd, passed=ok,
                       explanation=f"estimated cost ${out.cost_usd:.6f} <= ${max_usd}: {ok}")


DETERMINISTIC: dict[str, EvalFn] = {
    "exact_match": exact_match,
    "normalized_match": normalized_match,
    "contains": contains,
    "not_contains": not_contains,
    "regex": regex,
    "json_schema_valid": json_schema_valid,
    "numeric_tolerance": numeric_tolerance,
    "citation_correctness": citation_correctness,
    "context_precision_lexical": context_precision_lexical,
    "context_recall_lexical": context_recall_lexical,
    "groundedness_lexical": groundedness_lexical,
    "sql_result_match": sql_result_match,
    "status_match": status_match,
    "latency_threshold": latency_threshold,
    "cost_threshold": cost_threshold,
}
