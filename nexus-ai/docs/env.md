# NEXUS AI -- Environment variables

Copy `.env.example` to `.env`. All values are validated at startup by `app/core/config.py`.

| Variable | Default | Notes |
|---|---|---|
| APP_ENV | development | `production` enforces a strong JWT_SECRET (>= 32 chars, no placeholder) |
| DATABASE_URL | postgresql+psycopg://nexus:...@localhost:5441/nexus | psycopg 3 driver |
| TEST_DATABASE_URL | .../nexus_test | Used by pytest; schema is dropped and recreated |
| JWT_SECRET | dev placeholder | Required real secret in production |
| ACCESS_TOKEN_MINUTES | 60 | JWT lifetime |
| DEMO_USER_PASSWORD | placeholder | Password for all seeded demo users |
| CORS_ORIGINS | http://localhost:5171 | Comma-separated |
| LLM_PROVIDER | local | `local` (deterministic, no key), `gemini`, `openai` |
| GEMINI_API_KEY / GEMINI_MODEL_FAST / GEMINI_MODEL_STRONG | -- | Required when LLM_PROVIDER=gemini |
| OPENAI_API_KEY / OPENAI_MODEL_FAST / OPENAI_MODEL_STRONG | -- | Required when LLM_PROVIDER=openai |
| EMBEDDING_PROVIDER | local | `local` hashing, `gemini`, `openai` (all produce 384 dims) |
| GEMINI_EMBEDDING_MODEL / OPENAI_EMBEDDING_MODEL | see example | |
| WORKFLOW_TOKEN_BUDGET | 60000 | Per investigation run |
| WORKFLOW_STEP_TIMEOUT_S | 30 | Per step attempt |
| WORKFLOW_STEP_MAX_ATTEMPTS | 3 | Retries for transient failures |
| MAX_UPLOAD_MB | 15 | Upload and URL fetch limit |
| URL_INGEST_ALLOWLIST | example.com | Comma-separated hosts (subdomains allowed) |
| RATE_LIMIT_PER_MINUTE | 60 | Per user + route group, per process |
| INGESTION_MODE | embedded | `embedded` = API runs a worker thread; `worker` = separate process |
| STORAGE_DIR | backend/var/objects | Local object storage root |
| NEXUS_MCP_USER_EMAIL | analyst@acme.example | Service identity for the MCP server |

Switching EMBEDDING_PROVIDER after documents are indexed requires re-indexing (vectors from
different models are not comparable).
