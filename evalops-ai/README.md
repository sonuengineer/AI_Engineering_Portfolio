# EvalOps AI

LLM evaluation, benchmarking and observability platform. Define datasets of test cases, run them
against LLM prompt/model configs or black-box AI apps (NEXUS AI, DATAWISE AI) over HTTP, score the
outputs with deterministic evaluators (and optional LLM-judge estimates), trace every call, compare
runs to catch regressions, and gate CI on the result.

Part of the AI engineer portfolio workspace (see `../MASTER_ARCHITECTURE.md`). Ports: API 8103,
web 5173, Postgres 5443.

## Quick start (local dev)

Prerequisites: Docker, `uv` (Python 3.12 is fetched by uv), Node 24.

```bash
# 1. config
cd evalops-ai
cp .env.example .env            # then set DEMO_USER_PASSWORD (>= 10 chars) and JWT_SECRET

# 2. database
docker compose up -d db

# 3. backend: deps, migrations, seed (seed EXECUTES the demo runs), API + embedded worker
cd backend
uv venv -p 3.12 && uv sync
uv run alembic upgrade head
uv run python -m scripts.seed              # add --reset to wipe and rebuild
uv run uvicorn app.main:app --port 8103    # leave running

# 4. frontend (new terminal)
cd evalops-ai/frontend
npm install
npm run dev                                 # http://localhost:5173
```

Log in at http://localhost:5173 as `admin@evalops.local` (or `member@` / `viewer@`) with the
`DEMO_USER_PASSWORD` you put in `.env`.

Full stack in Docker instead: `docker compose up -d --build` then
`docker compose exec api python -m scripts.seed` (web on http://localhost:5173, API on 8103,
separate `worker` container). See `docs/setup-and-troubleshooting.md`.

## What is in the seed data

All runs below are produced by actually executing the engine at seed time with deterministic
providers -- no number is hand-written. The UI labels them "Deterministic local adapter / scripted
fixture -- not a real LLM".

| Project | Run | Provider | What it shows |
|---|---|---|---|
| Support Assistant QA | local-extractive baseline | `local` (rule-based extractive adapter) | honest baseline of a non-LLM: cites nothing, so citation metric fails |
| Support Assistant QA | scripted v1 (baseline) | `mock_scripted` script `v1` | good fixture outputs |
| Support Assistant QA | scripted v2 (candidate) | `mock_scripted` script `v2` | 8 deliberately broken cases -> regression detection, CI gate failure |
| Invoice Extraction | Extractor v1 / v2 | `mock_scripted` | JSON schema, numeric tolerance, regex, exact match |
| NEXUS AI RAG benchmark | (none until configured) | `http_nexus` | 32-case benchmark over NEXUS seed corpus |
| DATAWISE AI SQL benchmark | (none until configured) | `http_datawise` | 30 cases: 18 answerable (expected rows computed), 5 ambiguous, 7 unsafe |

To benchmark NEXUS / DATAWISE for real, start those apps, put their demo credentials in
`evalops-ai/.env` (`NEXUS_EMAIL`, `NEXUS_PASSWORD`, `DATAWISE_EMAIL`, `DATAWISE_PASSWORD`), then:

```bash
cd evalops-ai/backend
uv run python -m app.cli run --project nexus-rag --dataset nexus_rag_v1 --target "NEXUS AI (local dev)" --label "NEXUS live"
uv run python -m app.cli run --project datawise-sql --dataset datawise_sql_v1 --target "DATAWISE AI (local dev)" --label "DATAWISE live"
```

## CI gate

```bash
uv run python -m app.cli gate --run-id <candidate> --baseline <baseline> --thresholds ../evalops.gate.yaml
uv run python -m app.cli ci-gate --thresholds ../evalops.gate.yaml     # run candidate + gate in one step
```

Exit codes: 0 pass, 1 threshold/regression failure, 2 configuration error. The workspace workflow
`.github/workflows/evalops-ci.yml` runs lint, mypy, pytest (real Postgres), the frontend checks, and
an `eval-gate` job that also self-tests that the regressed v2 candidate is blocked.

## Docs

- `docs/architecture.md` -- components, ER diagram, run sequence
- `docs/evaluation-methodology.md` -- every metric, deterministic vs estimate, limitations
- `docs/api.md`, `docs/env.md`, `docs/setup-and-troubleshooting.md`, `docs/deployment.md`
- `docs/security-threat-model.md`, `docs/testing.md` (actual results), `docs/roadmap-and-limitations.md`
- `docs/adr/` -- architecture decision records
- `IMPLEMENTATION_STATUS.md` -- what is done, verified, untested or missing

## Live benchmark findings
EvalOps was run against the live NEXUS and DATAWISE APIs; results, a benchmark bug that was fixed via dataset v2, and evaluator design issues are documented in [docs/live-benchmark-findings.md](docs/live-benchmark-findings.md).
