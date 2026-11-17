# DATAWISE AI

Ask business questions in plain English and get **validated SQL, a chart and an insight whose
every number is computed from the returned rows** -- without ever executing SQL written by a model.

```
question -> guardrails -> planner (typed QueryPlan) -> compiler (our SQL) -> validator (sqlglot +
allowlists) -> read-only executor -> verifier + insight -> history + audit
```

## Why it is different

- **No free-form model SQL.** Planners (deterministic rules by default, Gemini/OpenAI optional)
  can only emit a Pydantic `QueryPlan`. SQL is compiled from a semantic layer of business metrics.
- **Defense in depth.** sqlglot validator (single SELECT, no DML/DDL anywhere in the tree,
  table/column/function allowlists, `LIMIT <= 1000`) + `datawise_reader` role (SELECT only,
  read-only transactions, cannot reach the users database) + statement timeout + row cap.
- **Honest ambiguity handling.** "Who are our best customers?" returns `needs_clarification` with
  one-click options ("by revenue", "by order count") instead of guessing.
- **Grounded insights.** "Revenue went from $236,420.60 in 2025-01 to $521,569.89 in 2025-12
  (+120.6%)" -- computed in Python from the rows, with provenance (columns + row indexes).
- **Measured.** 77-case evaluation with expected values from independent hand-written SQL,
  including a held-out paraphrase set that reports the planner's real limits (50%).

## Features

- Ask page: example questions, status, assumptions, generated SQL with copy button, validation
  result, Recharts line/bar chart chosen by the backend, result table, insight + provenance,
  clarification buttons, rejection messages, save as report
- History (org-scoped), Saved reports (re-run stored plan, delete), Catalog (information_schema +
  metric/dimension definitions)
- JWT + argon2 auth, org isolation, rate limiting, request ids, structured JSON logs, JSON error
  envelope, `/healthz` + `/readyz`
- "Deterministic local adapter" badge whenever the rule-based planner answered

## Quickstart (Docker)

```bash
cd datawise-ai
cp .env.example .env
docker compose up -d --build
```

Open http://localhost:5172 and sign in as `demo@acme.example` with the `DEMO_USER_PASSWORD` from
`.env` (a second org: `demo@globex.example`). API docs: http://localhost:8102/docs.
Stop with `docker compose down`.

Local dev servers (hot reload), tests and troubleshooting: [docs/setup-and-troubleshooting.md](docs/setup-and-troubleshooting.md).

## Try these

- Revenue by month in 2025
- Top 5 products by revenue last quarter
- Which region had the highest conversion rate in 2025?
- On-time delivery rate by supplier this year
- Revenue for Enterprise customers by month in 2026
- Who are our best customers?  (clarification)
- Delete all cancelled orders  (rejected)

## Status (verified 2026-11-16)

| Check | Result |
|---|---|
| Backend tests (real Postgres) | 149 passed |
| Frontend tests | 8 passed; typecheck + build clean |
| ruff / mypy / pip-audit / npm audit | clean |
| Evaluation (local planner) | 71/77 overall; 36/36 answered, 10/10 clarification, 12/12 unsafe, 7/7 edge, 6/12 held-out paraphrases |
| `docker compose up --build` from empty volume | works |

## Docs

[architecture](docs/architecture.md) | [api](docs/api.md) | [env](docs/env.md) |
[security threat model](docs/security-threat-model.md) | [testing](docs/testing.md) |
[evaluation](docs/evaluation.md) | [deployment](docs/deployment.md) |
[ADRs](docs/adr) | [roadmap and limitations](docs/roadmap-and-limitations.md)

## Stack

FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3, sqlglot, PostgreSQL 17, structlog,
React 19, TypeScript 5.9, Vite 7, Tailwind 4, Recharts 3, Vitest. Python 3.12 via uv, Node 24.
