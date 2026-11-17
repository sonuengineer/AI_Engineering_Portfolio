# Setup and troubleshooting

## One command sequence to start everything (dev)

```bash
cd evalops-ai
cp .env.example .env                                   # first time: set DEMO_USER_PASSWORD, JWT_SECRET
docker compose up -d db
cd backend && uv venv -p 3.12 && uv sync && uv run alembic upgrade head
uv run python -m scripts.seed                          # first time only (or --reset)
uv run uvicorn app.main:app --port 8103                # terminal 1 (worker runs inside)
cd ../frontend && npm install && npm run dev           # terminal 2 -> http://localhost:5173
```

On Windows with nvm-windows, make Node 24 available first (for example prefix the shell PATH with
the Node 24 install directory, or `nvm use 24`).

Docker alternative (everything containerized, separate worker):

```bash
cd evalops-ai
docker compose up -d --build
docker compose exec api python -m scripts.seed
# web http://localhost:5173  api http://localhost:8103
docker compose down            # stop (add -v to delete the database volume)
```

## Running tests

```bash
docker compose up -d db                     # creates evalops_test on first start
cd backend && uv run pytest -q ../tests
cd ../frontend && npm test && npm run typecheck && npm run build
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `DEMO_USER_PASSWORD must be set` | add it to `.env` (>= 10 chars) |
| `already seeded` | use `uv run python -m scripts.seed --reset` (wipes all EvalOps data) |
| pytest cannot connect / `evalops_test does not exist` | the init script only runs on a fresh volume: `docker exec evalops-db psql -U evalops -c "CREATE DATABASE evalops_test"` |
| runs stay `queued` | no worker: start the API with `RUN_WORKER_IN_API=true` or run `uv run python -m app.worker` |
| port 5443/8103/5173 busy | another process; stop it or change the compose port mapping |
| NEXUS/DATAWISE runs: every case errors "credentials are not configured" | set `NEXUS_EMAIL/NEXUS_PASSWORD` (or DATAWISE_*) in `evalops-ai/.env` and restart |
| HTTP target cases error "connection error" | target app not running on 8101/8102; in docker use `EVALOPS_DOCKER_*_URL` |
| judge metric shows `skipped: judge requires a configured LLM provider` | expected with `LLM_PROVIDER=local`; set a Gemini/OpenAI key and install the extra |
| `uv sync` removed google-genai/openai | plain `uv sync` installs only the base deps; use `uv sync --extra gemini --extra openai --extra otlp` |
| mojibake in a Windows terminal | all project files are ASCII; check your editor encoding |
