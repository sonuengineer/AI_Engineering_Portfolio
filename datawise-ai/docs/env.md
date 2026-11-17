# Environment variables

All settings are read by `backend/app/core/config.py` (pydantic-settings) from the environment or
from `datawise-ai/.env` (then `backend/.env`). Copy `.env.example` to `.env`. Every value in
`.env.example` is a local-development placeholder, not a secret.

| Variable | Default | Used by | Notes |
|---|---|---|---|
| POSTGRES_USER | datawise | compose db | superuser of the Postgres container, owner of both DBs |
| POSTGRES_PASSWORD | (required) | compose db | |
| DATAWISE_READER_PASSWORD | (required) | db init script | password of the read-only `datawise_reader` role |
| APP_DATABASE_URL | postgresql+psycopg://datawise:...@localhost:5442/datawise_app | API, Alembic, seed.py | SQLAlchemy URL |
| ANALYTICS_ADMIN_DATABASE_URL | postgresql://datawise:...@localhost:5442/datawise_analytics | seed_analytics.py, build_expected.py | never used by the API request path |
| ANALYTICS_READER_DATABASE_URL | postgresql://datawise_reader:...@localhost:5442/datawise_analytics | API executor, catalog, value index | read-only role |
| JWT_SECRET | dev placeholder | API | min 32 chars; set a random value outside dev |
| JWT_EXPIRES_MINUTES | 60 | API | access token lifetime |
| DEMO_USER_PASSWORD | change-me-demo-password | seed.py, run_eval.py | password of all seeded demo users |
| LLM_PROVIDER | local | API | `local` (deterministic rules), `gemini`, `openai` |
| GEMINI_API_KEY / GEMINI_MODEL | "" / gemini-2.5-flash | gemini provider | untested live |
| OPENAI_API_KEY / OPENAI_MODEL | "" / gpt-4.1-mini | openai provider | untested live |
| MAX_ROWS | 1000 | compiler, validator, executor | hard cap on rows returned |
| STATEMENT_TIMEOUT_MS | 5000 | executor | `SET LOCAL statement_timeout` per query |
| ANALYTICS_AS_OF_DATE | 2026-10-31 | planner | "today" for relative dates; end of synthetic data |
| CORS_ORIGINS | http://localhost:5172 | API | comma-separated |
| RATE_LIMIT_ASK_PER_MINUTE | 30 | API | per user + route token bucket (in-process) |
| LOG_LEVEL | INFO | API | structlog JSON |

Inside docker compose, the `api` service overrides the three database URLs to use host `db`.
