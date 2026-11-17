# Environment variables

All settings are read by `backend/app/core/config.py` (pydantic-settings) from the process
environment, then `.env` / `../.env`. `.env` is git-ignored; `.env.example` holds placeholders only.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | development | label only |
| `DATABASE_URL` | postgresql+psycopg://evalops:evalops_dev_password@localhost:5443/evalops | SQLAlchemy URL |
| `POSTGRES_PASSWORD` | evalops_dev_password | used by docker compose for the db container |
| `TEST_DATABASE_URL` | ...@localhost:5443/evalops_test | pytest database (created by `backend/scripts/init-test-db.sql`) |
| `JWT_SECRET` | dev placeholder | HS256 signing key -- set a long random value |
| `JWT_EXPIRE_MINUTES` | 60 | access token lifetime |
| `CORS_ORIGINS` | http://localhost:5173 | comma separated |
| `DEMO_USER_PASSWORD` | (none) | required by `scripts.seed` for the demo users |
| `LLM_PROVIDER` | local | default provider for the LLM judge (`local`, `gemini`, `openai`) |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | empty, gemini-2.5-flash | Gemini provider (needs `uv sync --extra gemini`) |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | empty, gpt-4o-mini | OpenAI provider (needs `uv sync --extra openai`) |
| `NEXUS_BASE_URL`, `NEXUS_EMAIL`, `NEXUS_PASSWORD` | http://localhost:8101 | `http_nexus` targets resolve these by name (`*_env` keys in target config) |
| `DATAWISE_BASE_URL`, `DATAWISE_EMAIL`, `DATAWISE_PASSWORD` | http://localhost:8102 | `http_datawise` targets |
| `EVALOPS_DOCKER_NEXUS_URL`, `EVALOPS_DOCKER_DATAWISE_URL` | http://host.docker.internal:810x | target URLs used inside docker compose |
| `RUN_WORKER_IN_API` | true | start the run worker thread inside the API process |
| `WORKER_POLL_SECONDS` | 1.0 | queue poll interval |
| `RATE_LIMIT_PER_MINUTE` | 240 | per user + route token bucket |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | 20 | per client IP |
| `MAX_UPLOAD_BYTES` | 5242880 | dataset upload limit (413 above) |
| `MAX_CASES_PER_UPLOAD` | 5000 | dataset case limit |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | empty | e.g. http://localhost:4318 -- enables OTLP/HTTP span export (`uv sync --extra otlp`) |
| `GIT_SHA` | empty | stored on runs; falls back to `git rev-parse HEAD` if available |
| `LOG_LEVEL` | INFO | structlog level |

Target credentials are never stored in the database: a target's `config` may only hold env var
*names* (`email_env`, `password_env`, `base_url_env`); keys that look like secrets are rejected with 422.
