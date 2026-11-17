# NEXUS AI -- Performance and evaluation methodology

## Latency (measured)

Reproduce: `cd backend && uv run python -m scripts.benchmark_latency` -> `docs/benchmarks/latency.json`.

Measured 2026-11-16 on the development machine (Windows 11, Python 3.12, Postgres in Docker),
providers `local`/`local`, in-process service calls without HTTP:

| Operation | n | p50 | p95 / max |
|---|---|---|---|
| chat ask (retrieve 2x25 candidates, fuse, rerank, answer, persist) | 30 | 37.9 ms | 52.1 ms (p95) |
| full investigation (6 agents, ~30 tool calls, 7 approvals) | 3 | 1330.6 ms | 1420.6 ms (max) |

These numbers describe the local adapter only. With Gemini/OpenAI, model latency (typically
seconds per call) dominates; the investigation makes 2 + N model calls (plan, analysis, one draft
per declining customer).

## Quality evaluation
Quality is evaluated by the separate **EvalOps AI** project (`../evalops-ai`), which calls the
`/api/v1/chat/ask` contract with a versioned golden dataset
(`evalops-ai/benchmarks/nexus_rag_v1.jsonl`) and computes deterministic metrics (citation
precision/recall against expected documents, lexical groundedness, abstention correctness,
latency). Judge-based metrics require a real LLM key and are labeled as estimates.

Inside this repo, the workflow integration tests act as a behavioural benchmark: the seed plants a
known cause for each declining customer (pricing, delivery, quality, budget, contract, and one
customer with no signal) and the tests assert that the investigation recovers each one without
false positives from shared documents.

No accuracy percentages are claimed here; see EvalOps run artifacts for measured numbers.

## Cost
Cost is estimated per call from `PRICE_TABLE` in `app/llm/base.py` (USD per 1M tokens, marked as
estimates to verify against current provider pricing) and stored in `usage_records`. The local
adapter reports cost 0 and character-based token estimates.
