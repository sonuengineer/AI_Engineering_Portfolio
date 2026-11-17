# Deployment

The repo ships `docker-compose.yml` with four services: `db` (postgres:17-alpine), `api`
(FastAPI; runs `alembic upgrade head` then uvicorn on 8103), `worker` (`python -m app.worker`,
SKIP LOCKED consumer), and `web` (nginx serving the Vite build and proxying `/api` to `api`).

Verified locally on 2026-11-16: `docker compose build` succeeded, the stack came up healthy, a run
created through the nginx proxy (port 5173) was executed by the separate worker container.

## Production checklist

- Set a strong `JWT_SECRET`, `POSTGRES_PASSWORD`; never bake `.env` into images (`.dockerignore`
  excludes it).
- Run `alembic upgrade head` as a one-off release step rather than on every API start if you run
  several API replicas.
- Scale workers horizontally; SKIP LOCKED guarantees a queued run is claimed once. A worker that dies
  mid-run leaves the run in `running` (no lease/heartbeat yet -- see roadmap).
- The in-process rate limiter is per replica; put a gateway limiter in front for real limits.
- Terminate TLS at a load balancer; restrict CORS_ORIGINS.
- Provider keys and target credentials come only from env/secret store.
- Optional: point `OTEL_EXPORTER_OTLP_ENDPOINT` at a collector (Jaeger/Tempo) after
  `uv sync --extra otlp` (image must be built with that extra).
- Back up the Postgres volume; traces grow with every run (no retention job yet).
