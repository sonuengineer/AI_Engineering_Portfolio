# Evaluation methodology

## Principles

1. **Deterministic metrics decide pass/fail.** A case passes when it has no execution error and every
   scored, gating, non-estimate metric passed. Skipped metrics (missing expectations) do not count.
2. **Judge metrics are estimates.** LLM-as-judge, DeepEval and RAGAS scores are stored with
   `is_estimate=true`, shown with an "estimate" badge, reported in comparisons, but never gate cases or
   the CI gate (ADR 0003).
3. **No fabricated scores.** The judge refuses with `local`/`mock_scripted` providers and records
   `skipped: judge requires a configured LLM provider`. Demo data comes from executing the engine.
4. **Reproducibility.** Each run stores a config snapshot (target, model params, prompt text + hash,
   evaluator configs, dataset version id + content hash, seed, concurrency/timeouts/retries, git sha).
   Deterministic providers produce identical outputs for the same dataset hash; latency differs.

## Metric catalog

| Type | Kind | Value | Passes when | Expectation source |
|---|---|---|---|---|
| exact_match | deterministic | 0/1 | trimmed strings equal | expected_output |
| normalized_match | deterministic | 0/1 | equal after lowercasing, removing punctuation, articles, extra spaces (`allow_containment` accepts expected inside output) | expected_output |
| contains | deterministic | fraction found | all found (or `mode=any`, or value >= threshold) | params.substrings / metadata.expected_keywords |
| not_contains | deterministic | 0/1 | no forbidden substring | metadata.must_not_contain |
| regex | deterministic | 0/1 | `re.search` matches (case-insensitive by default) | params.pattern / metadata.expected_regex |
| json_schema_valid | deterministic | 0/1 | output parses and validates (Draft 2020-12) | params.schema / metadata.json_schema |
| numeric_tolerance | deterministic | 0/1 | `math.isclose` with rel/abs tol; first number in text or `json_field` | metadata.expected_number / expected_output |
| citation_correctness | deterministic | citation recall | recall >= threshold (default 1.0); precision and F1 in details | expected_citations |
| context_precision_lexical | deterministic (heuristic) | share of retrieved contexts that overlap a reference context | >= threshold (0.5) | reference_contexts |
| context_recall_lexical | deterministic (heuristic) | share of reference contexts covered by retrieved text | >= threshold (1.0) | reference_contexts |
| groundedness_lexical | deterministic (heuristic) | share of answer sentences with token support in contexts | >= threshold (0.8) | retrieved contexts (or reference as fallback) |
| sql_result_match | deterministic | 1.0 or overlap share | rows equal as a multiset after rounding/normalizing | metadata.expected_rows |
| status_match | deterministic | 0/1 | target status equals expected | metadata.expected_status |
| latency_threshold | deterministic | latency ms | <= max_ms | params |
| cost_threshold | deterministic | cost USD | <= max_usd | params |
| llm_judge | judge (estimate) | 1-5 | >= threshold (default 4) | rubric + reference |
| deepeval / ragas | judge (estimate) | library score | library threshold | optional adapters |

### Lexical metric details and limitations

- Tokenization: lowercase alphanumeric tokens, English stopwords removed.
- Overlap of A in B = |distinct tokens(A) intersect tokens(B)| / |distinct tokens(A)|.
- `groundedness_lexical` ignores sentences with fewer than 3 content tokens ("Yes.").
- These are **heuristics**, not semantic judgments: paraphrases with different words score low;
  a sentence that reuses context words but contradicts the context ("not 30 days") can score as
  supported; negation and numbers are not reasoned about. Use them as cheap regression signals and
  pair them with exact keyword checks (`contains`, `not_contains`) or a judge estimate.
- Token counts for deterministic providers are estimated (~4 chars/token) and flagged
  `tokens_estimated`; costs for those runs multiply estimated tokens by configured demo prices and
  are therefore illustrative only.

## Aggregation

Per run: pass rate and mean per metric (over scored cases only), counts of scored/skipped/errors,
overall pass rate (over cases with at least one gating score), error rate, latency mean/p50/p95/max
(linear interpolation; errored cases excluded), total tokens, estimated cost, wall time and
throughput (cases/second).

## Comparison and regression detection

`compare(baseline, candidate)`: per metric `delta = candidate pass rate - baseline pass rate`;
regression if `delta < -tolerance` (absolute, default 0.02, per-metric overrides). Operational
regressions: overall pass rate drop, error rate increase above tolerance, p95 latency growth above
`latency_tolerance_pct` (and > 5 ms absolute). Case diff by `external_id`: newly failing, newly
passing, still failing, only-in-one-run. A warning is shown when dataset hashes differ.

## Benchmarks

- `benchmarks/nexus_rag_v1.jsonl` (32 cases): factual, numeric, why/reasoning, multi-document,
  prompt-injection (the intentionally malicious vendor note in the NEXUS corpus), tenant isolation
  (a Globex-only fact must not leak), unanswerable. Expected citations are NEXUS document titles taken
  from `nexus-ai/backend/app/seed_data/`; regenerate with `benchmarks/tools/build_nexus_benchmark.py`
  if that corpus changes.
- `benchmarks/datawise_sql_v1.jsonl` (30 cases): 18 answerable with expected rows **computed** by
  loading the DATAWISE data generator (fixed seed) into SQLite and running reference SQL written from
  the DATAWISE semantic layer definitions; 5 ambiguous (expect `needs_clarification`); 7 unsafe
  (expect `rejected`). Limitation: whether DATAWISE classifies a given question as ambiguous is its
  own design decision; failures there may reflect a disagreement in expectations, not a bug.
- `benchmarks/demo_*.jsonl`: demo datasets with scripted fixtures (see `tools/build_demo_datasets.py`).
