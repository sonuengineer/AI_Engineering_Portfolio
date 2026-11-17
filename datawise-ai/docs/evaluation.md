# Evaluation

## Dataset

`evaluation/datawise_eval.jsonl` -- 77 cases, built by `evaluation/build_expected.py`:

| Category | Cases | Expectation |
|---|---|---|
| answered | 38 | status `answered` AND a numeric check against the seeded data (includes 2 bare totals without a period, which default to all time) |
| paraphrase_holdout | 12 | same checks as an answered case, but the question is reworded; written AFTER the planner and NOT used to tune it |
| clarification | 8 | status `needs_clarification` (ranking without a measure, unknown metric, impossible breakdown, mixed facts, vague) |
| unsafe | 12 | status `rejected` (DML/DDL intent, users/passwords, pg_catalog, prompt injection, raw SQL, comment markers, tautology) |
| edge | 7 | out-of-range period (0 rows), HAVING threshold row count, two dimensions, value collision ("mobile"), "&" vs "and" + upper case, last 30 days, unknown long question |

Check types: `scalar` (first row value), `top` (first row name + value), `series` (every
dimension value -> metric value), `row_count`.

### Independence of expected values

Expected values come from hand-written SQL on the ADMIN connection, phrased differently from the
compiler (EXTRACT/BETWEEN/CASE/`::numeric` vs DATE_TRUNC/CAST/AVG of booleans, subqueries vs joins).
The system under test is never called while building expectations. Because the seed is fixed,
the values are reproducible: a fresh volume produced identical results.

## Runner

```bash
cd datawise-ai
backend/.venv/Scripts/python evaluation/build_expected.py      # Linux/macOS: backend/.venv/bin/python
backend/.venv/Scripts/python evaluation/run_eval.py --password "<DEMO_USER_PASSWORD>"
```

`run_eval.py` only uses the public HTTP contract (login + ask), retries on 429, and writes
`evaluation/results/latest.json`. `--min-accuracy` turns it into a CI gate (CI uses 0.90).

## Actual results (2026-11-16, provider=local, docker compose stack, fresh volume)

```
DATAWISE eval -- provider=local cases=77
  answered              36/36  (100.0%)
  paraphrase_holdout     6/12  (50.0%)
  clarification         10/10  (100.0%)
  unsafe                12/12  (100.0%)
  edge                   7/7   (100.0%)
  OVERALL               71/77  (92.2%)
  server latency p50=21 ms p95=48 ms
```

Saved copy: `evaluation/results/baseline-local-2026-11-16.json`.

## Policy change and re-run (2026-11-17)

Product decision: a bare total without a period ("What were sales?", "Show revenue") now answers
over **all available data** and states the assumption ("No period given: using all available data
(start to end)") instead of asking "For which period?". Two cases moved from `clarification` to
`answered`; their expected values come from the same independent all-time revenue SQL as
`rev_all_time`. Real ambiguity (ranking without a measure, unknown metrics, impossible breakdowns)
still asks.

```
  answered              38/38  (100.0%)
  paraphrase_holdout     6/12  (50.0%)
  clarification          8/8   (100.0%)
  unsafe                12/12  (100.0%)
  edge                   7/7   (100.0%)
  OVERALL               71/77  (92.2%)
  server latency p50=73 ms p95=144 ms   (measured right after an API container restart)
```

### How to read these numbers

- The 100% categories were written by the same author as the rule-based planner, so they measure
  **correctness of the pipeline on supported phrasings** (compiler, joins, filters, time math,
  insight numbers, safety), not language understanding.
- The **held-out paraphrase score (50%)** is the honest generalization number for the
  deterministic planner. Failures were:
  - "best converting traffic source last year" -> "converting" matched the metric but "traffic
    source" was not treated as a grouping (no cue word before it)
  - "how reliable were our vendors in 2026" -> "reliable" is not a synonym of on-time rate
  - "biggest spending customers in 2025" -> "spending" is not a synonym of revenue
  - "total takings for the third quarter of 2025" -> "takings" unknown
  - "avg order size during 2025" -> synonym is "average order size", "avg" variant missing
  - "how many days does delivery take on average" -> phrase not covered
  Every failure was a safe failure: `needs_clarification` or an answer missing a breakdown --
  never a wrong number presented as correct.
- These failures are intentionally NOT fixed to keep the holdout meaningful. They are the
  motivating case for the LLM planner providers (same typed plan, same validator).

## Not evaluated

- Gemini / OpenAI planners (no API keys available). Run the same command with `LLM_PROVIDER=gemini`
  and compare; the dataset and runner are provider-agnostic.
- Latency under concurrent load.
