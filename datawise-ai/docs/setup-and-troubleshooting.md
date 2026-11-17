# Setup and troubleshooting

## Option A -- everything in Docker (recommended demo path)

```bash
cd datawise-ai
cp .env.example .env            # placeholders are fine for local use
docker compose up -d --build    # db -> api (migrations + seeds on start) -> web
# open http://localhost:5172 and sign in as demo@acme.example / value of DEMO_USER_PASSWORD
docker compose down             # stop (add -v to also delete the database volume)
```

The api container runs `alembic upgrade head`, `scripts.seed` and `scripts.seed_analytics` on each
start (`RUN_MIGRATIONS_AND_SEED=1`); all three are idempotent. First start on an empty volume takes
about 10-20 seconds (verified).

## Option B -- local dev servers (hot reload)

Prerequisites: Docker, `uv`, Node 24 (`nvm use 24`; `.nvmrc` provided).

```bash
cd datawise-ai
cp .env.example .env
docker compose up -d db                              # Postgres on localhost:5442

cd backend
uv venv -p 3.12 && uv sync                           # Python 3.12 (system python may be newer)
uv run alembic upgrade head
uv run python -m scripts.seed                        # demo users
uv run python -m scripts.seed_analytics              # synthetic data (use --reset to rebuild)
uv run uvicorn app.main:app --reload --port 8102

# second terminal
cd datawise-ai/frontend
npm install
npm run dev                                          # http://localhost:5172 (proxies /api to 8102)
```

Windows note: on this machine `nvm use` is not required if you put Node 24 first on PATH, e.g.
`export PATH="/c/Users/<you>/AppData/Local/nvm/v24.21.0:$PATH"` in Git Bash.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `port is already allocated` for 5442/8102/5172 | another stack or a dev server is running | stop it (`docker ps`, or kill the uvicorn/vite process) |
| `/readyz` returns 503 with `analytics_db: unavailable` | reader role missing (volume created before the init script existed) or wrong `DATAWISE_READER_PASSWORD` | `docker compose down -v && docker compose up -d` (init script only runs on an empty volume) |
| `password authentication failed for user "datawise_reader"` | `.env` reader password changed after the volume was initialized | reset the volume or `ALTER ROLE datawise_reader PASSWORD '...'` as the admin user |
| Login returns 401 | `DEMO_USER_PASSWORD` changed after seeding | re-run `python -m scripts.seed` (it resets demo passwords) |
| Every question returns `needs_clarification` for a period | bare totals without a period are intentionally ambiguous | add a period ("in 2025", "last month") or click an option |
| Questions about 2023 return no rows | synthetic data covers 2024-11-01..2026-10-31 | expected; insight says "No data matched" |
| `uv venv` picks Python 3.14 | system Python is newer | always `uv venv -p 3.12` |
| Frontend `npm install` warns about esbuild install scripts | npm allowScripts policy | harmless; build and tests were verified with this warning |
| `db/init/01-init.sh: not found` in container logs | file checked out with CRLF line endings | `.gitattributes` forces LF for `*.sh`; re-checkout or convert |
