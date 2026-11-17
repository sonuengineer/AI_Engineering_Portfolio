# Live benchmark findings: NEXUS and DATAWISE (2026-11-16)

These runs executed the EvalOps engine against the **running** NEXUS (http://localhost:8101) and
DATAWISE (http://localhost:8102) APIs over HTTP. Both systems were using their deterministic local
adapters (no LLM API keys). Raw summaries: `docs/benchmarks/live-benchmarks.json`, exported verbatim
from stored runs by `backend/scripts/export_run_summaries.py`.

## How to reproduce
```bash
cd evalops-ai/backend
# credentials of the NEXUS/DATAWISE demo users (taken from those projects' .env)
export NEXUS_EMAIL=analyst@acme.example NEXUS_PASSWORD=<nexus DEMO_USER_PASSWORD>
export DATAWISE_EMAIL=demo@acme.example DATAWISE_PASSWORD=<datawise DEMO_USER_PASSWORD>
uv run python -m app.cli run --project nexus-rag --dataset nexus_rag_v1 --target "NEXUS AI (local dev)" --label "NEXUS live ..."
uv run python -m app.cli run --project datawise-sql --dataset datawise_sql_v1 --target "DATAWISE AI (local dev)" --label "DATAWISE live ..."
uv run python -m scripts.export_run_summaries --label-prefix "NEXUS live" --label-prefix "DATAWISE live" --out ../docs/benchmarks/live-benchmarks.json
```

## NEXUS RAG (32 cases)

| Metric | Dataset v1 | Dataset v2 |
|---|---|---|
| citations (expected document cited) | 63.3% | 63.3% |
| groundedness (lexical heuristic) | 62.5% | 62.5% |
| context_recall (lexical) | 100% | 100% |
| context_precision (lexical) | 13.3% | 13.3% |
| unanswerable_refusal | **0/2** | **2/2** |
| no_leak_or_injection | 2/2 | 2/2 |
| latency under 10 s | 100% (p50 ~72 ms) | 100% |
| overall case pass rate (all gating metrics must pass) | 6.25% | 6.25% |

Findings:
1. **Benchmark bug, fixed via a new dataset version.** v1's refusal regex did not accept NEXUS's
   phrasing ("I could not find enough evidence..."), so two correct refusals scored 0. Dataset v2
   (content hash `6ab9d90d55d4`) adds `could not find|not enough evidence`. v1 and its run are kept
   for auditability; only the refusal metric changed.
2. **Real NEXUS weakness: low recall on paraphrased questions.** About 10 answerable questions got
   the abstention response because NEXUS's local extractive adapter requires >= 60% question-term
   coverage in a single sentence. Paraphrases ("legal team ask to change" vs "requested changes to
   the liability clause") miss. This was deliberately NOT tuned away: it is the expected limitation
   of a lexical adapter and the main argument for running NEXUS with a real LLM.
3. **Evaluator design issue: groundedness penalizes correct refusals.** A refusal sentence has no
   support in retrieved contexts, so cases nx-031/nx-032 fail groundedness although the behavior is
   correct. Proposed fix: skip groundedness when the case expects abstention (roadmap).
4. **context_precision is strict for top-k retrieval.** NEXUS returns 6 contexts; most cases expect
   one source document, so precision is low by construction. Treat as a retrieval-precision signal,
   not a correctness verdict.

## DATAWISE SQL (30 cases)

| Metric | Result |
|---|---|
| status match (answered / needs_clarification / rejected) | 25/30 (83.3%) |
| result rows match expected rows | 13/18 scored (72.2%) |
| latency under 10 s | 100% (p50 ~64 ms) |

All 5 failures are the same behavior: for all-time aggregates without a period (e.g. total
revenue), DATAWISE asks "For which period do you want ...?" while the benchmark expects an
answer. This is a product decision (DATAWISE prefers clarification over guessing a time range), not a
wrong number; no case returned incorrect rows. Either the benchmark or the planner policy should be
changed deliberately -- recorded here rather than silently "fixed".

## What these numbers do not mean
They describe the local, rule-based adapters of NEXUS and DATAWISE on these specific datasets. They
are not quality claims for any LLM.

## Follow-up runs (2026-11-17)

Two changes were made in response to the findings above, then both benchmarks were re-run against
the live APIs (all runs are kept in `docs/benchmarks/live-benchmarks.json`):

1. **EvalOps:** `groundedness_lexical` now skips cases tagged `unanswerable` (configurable via
   `skip_tags`): correct refusals are judged by the refusal metric instead of failing groundedness.
   Regression test: `tests/test_evaluators.py::test_groundedness_skips_expected_abstentions`.
2. **DATAWISE:** product decision -- a bare total without a period answers over all available data
   and states that assumption, instead of asking "For which period?".

| Run | Before | After |
|---|---|---|
| NEXUS groundedness | 62.5% (20/32, refusals counted as failures) | 66.7% (20/30, refusals skipped) |
| NEXUS overall case pass rate | 6.25% | 12.5% |
| DATAWISE status match | 25/30 | 30/30 |
| DATAWISE result rows | 13/18 | 18/18 |

NEXUS retrieval/citation metrics are unchanged (no NEXUS code changed). Latency in these runs is
higher (p50 ~210-270 ms) because the containers had just been restarted; the earlier ~65-72 ms p50
reflects warm services.
