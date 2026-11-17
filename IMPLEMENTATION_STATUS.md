# Implementation Status (workspace root)

Last updated: 2026-11-16 (end of autonomous session). All numbers below come from the final
verification sweep run at the end of the session.

## Final verification
| Project | Backend tests | Lint / types | Frontend unit | Browser e2e (Playwright) | Docker |
|---|---|---|---|---|---|
| nexus-ai | 88 passed (real Postgres + pgvector) | ruff + mypy clean | 4 passed | 4 passed (against Docker stack :8081) | api, worker, web, db healthy |
| datawise-ai | 149 passed (real Postgres, read-only role) | ruff + mypy clean | 8 passed | 3 passed (:5172) | api, web, db healthy |
| evalops-ai | 67 passed (real Postgres) | ruff (CI scope) + mypy clean | 15 passed | 2 passed (:5173) | api, worker, web, db healthy |
| portfolio | -- | tsc clean | 5 passed | 4 passed | nginx image serving on :8090 |

Evaluation artifacts (all produced by running code):
- nexus-ai/docs/benchmarks/latency.json -- chat p50 37.9 ms / p95 52.1 ms; investigation ~1.33 s (local adapter).
- datawise-ai/docs/benchmarks/eval-summary.json -- 71/77 (92.2%); held-out paraphrases 6/12; all failures safe.
- evalops-ai/docs/benchmarks/live-benchmarks.json -- EvalOps runs against the LIVE NEXUS and DATAWISE APIs.

Interview handbooks (validated: every code reference exists, ASCII only):
- nexus-ai 121 Q, datawise-ai 119 Q, evalops-ai 125 Q, cross-project 32 Q.

## Defects found and fixed during verification
- NEXUS: off-topic citations / answering off-corpus questions; multi-customer spreadsheet leaking into
  per-customer evidence; benign phrases triggering hypotheses; startup recovery breaking runs of other
  replicas; denied tool-call audits lost on rollback; login timing oracle; orphaned blobs on delete;
  missing .gitignore (would have committed .env).
- DATAWISE: rate-limit bypass via per-report buckets; login timing oracle; table row numbering.
- EVALOPS: benchmark refusal-regex false negative (fixed as immutable dataset v2); benchmark builder
  drift; blocking sync work inside an async upload handler.
- All frontends: chart draw-in animation captured mid-render; vitest collecting Playwright specs.

## Not done / needs external resources
- Live LLM providers (Gemini/OpenAI), LLM judge, DeepEval/RAGAS, OTLP export: need API keys.
- Cloud deployment: needs AWS credentials. CI workflows never ran on GitHub (no remote repo).
- See each project's docs/roadmap-and-limitations.md and TODO.md.
