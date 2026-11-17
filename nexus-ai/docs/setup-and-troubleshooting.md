# NEXUS AI -- Local setup and troubleshooting

## Prerequisites
Docker (for Postgres), Python 3.12 via `uv`, Node 24 (`nvm use 24`; Node >= 20.19 also works).

## Run locally (recommended for development)

```bash
cd nexus-ai
cp .env.example .env                 # set DEMO_USER_PASSWORD (and JWT_SECRET)
docker compose up -d db              # Postgres 17 + pgvector on localhost:5441

cd backend
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed        # add --reset to wipe and reseed
uv run uvicorn app.main:app --port 8101

# second terminal
cd nexus-ai/frontend
npm ci
npm run dev                          # http://localhost:5171
```

Log in as `manager@acme.example` (or analyst/viewer/admin @acme.example, admin@globex.example)
with the password from `DEMO_USER_PASSWORD`.

## Run everything in Docker

```bash
cd nexus-ai && cp .env.example .env
docker compose --profile full up --build     # web: http://localhost:8081, API: :8101
```

## Tests

```bash
cd nexus-ai/backend && uv run pytest                    # needs `docker compose up -d db`
cd nexus-ai/frontend && npx vitest run
# e2e (needs API on :8101 and Vite on :5171, freshly seeded):
npx playwright install chromium && npx playwright test
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `connection refused` on 5441 | `docker compose up -d db`; check `docker ps` |
| `database "nexus_test" does not exist` | The init script only runs on a fresh volume: `docker exec nexus-db createdb -U nexus nexus_test` |
| Documents stuck in `pending` | No worker: keep `INGESTION_MODE=embedded` for local dev, or run `uv run python -m app.worker` |
| Vitest: "failed to find the current suite" on Windows | The shell's drive letter is lowercase (`h:`) while Node resolves `H:`, loading vitest twice. Run from an uppercase path (`cd H:\...`) |
| Login works but every call returns 401 | JWT_SECRET changed after login; sign in again |
| `LLM_PROVIDER=gemini requires GEMINI_API_KEY` at boot | Settings validation refuses inconsistent config by design |
| Answers say "insufficient evidence" | The local adapter abstains when the best sentence covers < 60% of the question terms. Rephrase with document terms or configure a real LLM |
| Port 8101/5171 in use | Another instance is running; stop it or change ports in vite.config.ts / uvicorn |
