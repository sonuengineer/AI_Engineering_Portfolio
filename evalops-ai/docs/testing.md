# Testing

All numbers below are from actual runs on 2026-11-16 (Windows 11, Python 3.12.x via uv,
Node 24.21.0, Postgres 17 in docker container `evalops-db`).

## Backend: 67 passed, 0 failed

`cd backend && uv run pytest -q ../tests` -> `67 passed` (about 23-30 s). Tests run against a real
Postgres database (`evalops_test`); the schema is rebuilt with Alembic at session start and tables
are truncated after each test. Mocks are used only at external boundaries (provider SDK factory,
`httpx` transport for NEXUS/DATAWISE).

| File | Tests | What it covers |
|---|---|---|
| test_evaluators.py | 13 | every deterministic evaluator incl. skip/err paths, evaluator crash capture |
| test_datasets.py | 11 | JSONL validation (8 rejection cases), limits, stable content hash |
| test_aggregation.py | 8 | percentiles, case pass logic (estimates never gate), summary, regression detection, tolerances, case diff, thresholds |
| test_engine.py | 9 | worker claim + execute, SKIP LOCKED single claim, local provider tokens/cost/traces, PII redaction in stored spans, scripted regression, retries with backoff then success, error capture after max retries, failed run, NEXUS/DATAWISE contract mapping (token caching, 503 -> transient), missing credentials |
| test_api.py | 9 | health, error envelope + request id, roles, upload validation/versioning/413, secret rejection in target config, full run lifecycle (create -> worker -> results -> compare -> traces -> JSON/MD/CSV reports), tenant isolation across 10 endpoints, rate limiting |
| test_judge.py | 5 | judge refuses with `local` and with unconfigured real provider, structured score parsing, invalid output -> error, deepeval/ragas adapters skip when unavailable |
| test_gate_cli.py | 5 | exit codes 0/1/2, regression-only gating, incomplete run, `ci-gate` end to end |
| test_redaction.py | 7 | emails, phones, bearer/API keys/JWT/kv secrets, Luhn cards, no false positives on dates/amounts, recursive key masking |

Bugs the tests caught during development (fixed): the phone regex partially masked non-card
16-digit numbers; the gate CLI crashed printing the report for a non-completed run; logging to a
captured stream broke under pytest.

Static checks: `uv run ruff check app scripts ../tests ../benchmarks/tools` -> clean;
`uv run mypy app scripts` -> `Success: no issues found in 46 source files`.

## Frontend: 15 passed, 0 failed

`cd frontend && npm test` -> `Test Files 6 passed (6), Tests 15 passed (15)`;
`npm run typecheck` clean; `npm run build` succeeds.

| File | Tests |
|---|---|
| src/api/client.test.ts | 3 (error envelope -> ApiError, 401 handling) |
| src/components/MetricCard.test.tsx | 3 (estimate badge, skip reason) |
| src/components/spanLayout.test.ts | 4 (waterfall offsets/depth) |
| src/components/CompareTable.test.tsx | 2 (regression/improvement highlighting) |
| src/pages/LoginPage.test.tsx | 2 (submit, error) |
| src/lib/useRunPolling.test.tsx | 1 (polling stops on terminal status) |

Manual browser check (by the frontend build agent, headless Chromium): admin and viewer logins,
viewer sees no write actions, run detail cards/charts/filters/trace links, report downloads,
compare v1 vs v2 shows the regressions and 8 newly failing cases, trace waterfall, no console
errors, no horizontal scroll at 375 px. Not exercised in a browser: submitting a new run and
uploading a JSONL file through the UI (both are covered by API tests).

## End-to-end checks performed

- `scripts.seed --reset` executes 5 demo runs (see README table).
- `python -m app.cli ci-gate --thresholds ../evalops.gate.yaml` -> exit 0; with
  `--target "Scripted assistant v2"` -> exit 1 listing the regressions and 8 newly failing cases.
- The CI `eval-gate` job steps were replayed locally on a fresh database (`evalops_ci`): migrate,
  seed, gate pass (exit 0), regressed self-test (exit 1).
- `docker compose up -d --build`: all services healthy, a run created via the nginx proxy was
  completed by the `worker` container.

## Not tested

- Gemini/OpenAI providers, the LLM judge with a real provider, the DeepEval/RAGAS adapter bodies,
  and OTLP export against a live collector (no keys/collector in the build environment).
- Live NEXUS/DATAWISE benchmark runs (their APIs answered /healthz, but EvalOps was not given their
  demo credentials); the HTTP contract mapping is tested with mocked transports.
- The GitHub Actions workflow itself has not run on GitHub.

## Browser e2e (Playwright) -- added during final verification
`frontend/e2e/demo.spec.ts`, run against the Docker stack (web :5173): **2 passed** (live NEXUS run
detail with metric cards and per-case table; comparing two runs shows metric deltas and case changes).
Screenshots in `docs/screenshots/`.

The e2e suite logs in as a dedicated viewer account created with the admin CLI (the password comes
from an environment variable, never argv):
```bash
cd backend && NEW_USER_PASSWORD=<12+ chars> uv run python -m scripts.create_user --org acme-eval --email e2e-viewer@evalops.local --role viewer
cd ../frontend && E2E_PASSWORD=<same> npx playwright test
```
Note: the account `e2e-viewer@evalops.local` exists in the local dev database (viewer role, local-only
password `e2e-viewer-local-only`). Delete or reset it before any shared deployment.

## Live benchmarks against NEXUS and DATAWISE
See `docs/live-benchmark-findings.md`.
