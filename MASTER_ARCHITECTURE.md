# Master Architecture -- AI Engineer Portfolio Workspace

This workspace holds three independently deployable AI products plus a portfolio site.
Each project is self-contained (own backend, frontend, database, compose file, CI workflow,
docs). Nothing is imported across project boundaries; the only coupling is HTTP contracts
(EvalOps calls NEXUS and DATAWISE as black-box targets).

```
ai-engineer-portfolio/
  nexus-ai/        Enterprise intelligence: RAG + LangGraph agents + approvals
  datawise-ai/     Natural-language BI: semantic layer -> query plan -> validated SQL
  evalops-ai/      LLM evaluation + tracing + CI regression gates
  portfolio/       Static recruiter-facing site + interview prep UI
  .github/workflows/  One CI workflow per project (path-filtered)
```

## 1. Shared conventions (each project re-implements; no shared package)

| Concern | Decision |
|---|---|
| Python | 3.12, managed with `uv`, deps pinned in `backend/pyproject.toml` + `uv.lock` |
| Web framework | FastAPI + Pydantic v2 + pydantic-settings |
| DB access | SQLAlchemy 2 (sync engine, psycopg 3 driver), Alembic migrations |
| Database | PostgreSQL 17 (NEXUS uses `pgvector/pgvector:pg17`) |
| Auth | JWT (HS256, short-lived access token), argon2 password hashing, role-based checks |
| Multi-tenancy | `org_id` column on every tenant-owned row; every query filters by the caller's org |
| Logging | structlog JSON logs, request-id middleware (`X-Request-ID`), no secrets/prompts in logs |
| Health | `GET /healthz` (process up), `GET /readyz` (DB reachable) |
| Errors | JSON `{ "error": { "code", "message", "request_id" } }` |
| Rate limiting | In-process token bucket per user+route (documented limitation: not shared across replicas) |
| Frontend | React 19 + TypeScript 5.9 + Vite 7 + Tailwind 4, Vitest + Testing Library |
| Node | 24 (see `.nvmrc`); `nvm use 24` |
| Tests | pytest against a real Postgres (docker compose service), mocks only at external boundaries |
| Lint/type | ruff + mypy (backend), `tsc --noEmit` + eslint-free strict TS (frontend) |

### Backend layout (all three projects)

```
backend/
  app/
    main.py            FastAPI app factory, middleware, routers
    core/              config.py, db.py, security.py, logging.py, errors.py, ratelimit.py
    models/            SQLAlchemy ORM models
    schemas/           Pydantic request/response models
    services/          Business logic (no FastAPI imports)
    api/               Routers (thin: validate -> call service -> serialize)
    llm/               Provider abstraction: base.py, local.py, gemini.py, openai_provider.py
  alembic/             Migrations
  scripts/seed.py      Reproducible synthetic data (fixed random seed)
  pyproject.toml
tests/                 pytest suite (project root, outside backend/)
```

### LLM provider abstraction

`LLM_PROVIDER=local|gemini|openai` (default `local`).

- `local` is a **deterministic, rule-based adapter**. It never pretends to be an LLM: every
  API response carries `"provider": "local"` and the UI shows a "Deterministic local adapter"
  badge. It exists so demos and tests run without paid keys.
- `gemini` uses `google-genai` (`client.models.generate_content(..., config=GenerateContentConfig(response_mime_type="application/json", response_json_schema=...))`).
- `openai` uses the `openai` SDK chat completions with JSON schema response format.
- All providers return a Pydantic-validated structured object plus a `Usage` record
  (input/output tokens, estimated cost, latency). Invalid structured output -> one repair retry -> typed error.

## 2. Ports (local dev)

| Project | API | Web (vite dev) | Postgres (host) |
|---|---|---|---|
| NEXUS | 8101 | 5171 | 5441 |
| DATAWISE | 8102 | 5172 | 5442 |
| EVALOPS | 8103 | 5173 | 5443 |
| Portfolio | -- | 5170 | -- |

## 3. Cross-project HTTP contracts (used by EvalOps targets)

### NEXUS AI

```
POST /api/v1/auth/login        {"email","password"} -> {"access_token","token_type":"bearer"}
POST /api/v1/chat/ask          Authorization: Bearer <t>
  body: {"question": str, "conversation_id": str | null}
  200:  {"conversation_id", "answer", "provider", "model",
         "citations": [{"chunk_id","document_id","document_title","page","snippet"}],
         "contexts": [str],             # retrieved chunk texts given to the generator
         "usage": {"input_tokens","output_tokens","estimated_cost_usd"},
         "latency_ms": int}
```

### DATAWISE AI

```
POST /api/v1/auth/login        {"email","password"} -> {"access_token","token_type":"bearer"}
POST /api/v1/questions/ask     Authorization: Bearer <t>
  body: {"question": str}
  200:  {"status": "answered" | "needs_clarification" | "rejected",
         "plan": object | null, "sql": str | null,
         "validation": {"ok": bool, "issues": [str]},
         "columns": [str], "rows": [[any]], "row_count": int,
         "insight": str | null, "clarification": {"question","options":[str]} | null,
         "rejection_reason": str | null, "provider", "latency_ms": int}
```

Demo credentials are created by each project's seed script from `DEMO_USER_PASSWORD`
(placeholder in `.env.example`; never a real secret).

## 4. Key cross-cutting decisions (details in each project's docs/adr)

1. **Deterministic local adapters over fake LLM output** -- honest demos without keys.
2. **Postgres-backed job queue (`SELECT ... FOR UPDATE SKIP LOCKED`) instead of Celery** for
   NEXUS ingestion -- one fewer moving part; Redis is not required for the vertical slice.
3. **DATAWISE never executes free-form model SQL**: model output is a typed `QueryPlan`
   compiled to SQL by our code, then re-parsed by sqlglot and checked against allowlists, and
   executed under a read-only role with `statement_timeout` and a row limit.
4. **EvalOps separates deterministic metrics from judge metrics**; judge scores are labeled
   "estimate" everywhere and never mixed into deterministic pass/fail unless configured.
