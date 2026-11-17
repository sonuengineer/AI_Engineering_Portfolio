# EvalOps AI -- implementation status

Last updated: 2026-11-16. Legend: DONE+VERIFIED (ran it), DONE (built, partially verified),
UNTESTED (implemented, never executed against the real dependency), NOT DONE.

| Area | Status | Notes |
|---|---|---|
| Domain model + Alembic migration (18 tables) | DONE+VERIFIED | `alembic/versions/0001_initial_schema.py` |
| Auth (JWT HS256 + argon2), roles, org scoping, audit, request id, JSON errors, rate limits | DONE+VERIFIED | API tests incl. tenant isolation |
| Datasets: JSONL upload, validation, size/type limits, immutable hashed versions | DONE+VERIFIED | |
| Prompts (versioned, hashed), model configs, targets, evaluator configs, experiments | DONE+VERIFIED | create via API; UI lists them read-only |
| Providers `local`, `mock_scripted` | DONE+VERIFIED | |
| Providers `gemini`, `openai` | UNTESTED | SDK signatures verified by introspection (google-genai 3.3.0, openai 3.51.0) |
| Run engine: concurrency, timeout, retries + backoff, error capture, snapshot, SKIP LOCKED worker | DONE+VERIFIED | embedded worker and compose worker container both exercised |
| 15 deterministic evaluators (incl. not_contains) | DONE+VERIFIED | unit tested |
| LLM-as-judge | DONE (refusal path verified; scoring parsed with mocked provider) / live UNTESTED | |
| DeepEval / RAGAS adapters | UNTESTED | APIs introspected in scratch venvs (deepeval 4.3.4, ragas 0.4.4); skip path tested; not uv extras (openai conflict) |
| Aggregation, comparison, regression detection, case diff | DONE+VERIFIED | |
| Tracing + redaction | DONE+VERIFIED | OTLP export UNTESTED (no collector) |
| Gate CLI (`gate`, `run`, `ci-gate`) + `evalops.gate.yaml` | DONE+VERIFIED | exit codes 0/1/2 tested |
| Reports JSON / Markdown / CSV (API + UI download) | DONE+VERIFIED | |
| Benchmarks nexus_rag_v1 (32), datawise_sql_v1 (30) | DONE | aligned with sibling seed data; live runs NOT DONE (no credentials for EvalOps) |
| Seed script (executes 5 demo runs) | DONE+VERIFIED | |
| Frontend dashboard (login, projects, datasets/cases, runs, run detail, compare, traces, new run) | DONE+VERIFIED | 15 vitest tests, build OK, browser-checked; new-run submit + upload not clicked through in a browser |
| Docker: backend/frontend Dockerfiles, compose (db, api, worker, web) | DONE+VERIFIED | |
| CI workflow `.github/workflows/evalops-ci.yml` incl. eval-gate | DONE | eval-gate steps replayed locally; never run on GitHub |
| Docs + 5 ADRs | DONE | |
| Interview handbook | NOT DONE | placeholder only, by instruction |

## TODO / follow-ups

- Run the NEXUS/DATAWISE benchmarks live: set `NEXUS_EMAIL/PASSWORD`, `DATAWISE_EMAIL/PASSWORD` in
  `evalops-ai/.env` and use the `app.cli run` commands from README.md. Expect some DATAWISE
  ambiguous-case "failures" to be expectation disagreements; review before treating as bugs.
- NEXUS citation expectations use document titles read from `nexus-ai/backend/app/seed_data/` on
  2026-11-16; rerun `benchmarks/tools/build_nexus_benchmark.py` after corpus changes.
- See docs/roadmap-and-limitations.md for engineering gaps (worker leases, egress allowlist, CSP).
