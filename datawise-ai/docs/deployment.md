# Deployment

The repository ships a production-shaped (not production-hardened) stack:

| Service | Image | Notes |
|---|---|---|
| db | postgres:17-alpine | init script creates both DBs + `datawise_reader`; volume `datawise_pgdata` |
| api | backend/Dockerfile (python:3.12-slim + uv, non-root uid 10001) | `RUN_MIGRATIONS_AND_SEED=1` bootstraps on start; healthcheck hits `/readyz` |
| web | frontend/Dockerfile (node:24-alpine build -> nginx:1.29-alpine) | serves SPA, proxies `/api/` to `api:8102`, sets basic security headers |

`docker compose up -d --build` was run successfully, including from an empty volume.

## Moving beyond a single host

1. **Managed Postgres**: create `datawise_app`, `datawise_analytics` and `datawise_reader` with the
   same SQL as `db/init/01-init.sh`; give the API two connection strings (app user, reader).
   In production the app DB user should not be a superuser -- create a dedicated owner role.
2. **Migrations and seeding as a job**: set `RUN_MIGRATIONS_AND_SEED=0` on API replicas and run
   `alembic upgrade head` once per release (CI/CD job or init container). Do not run
   `seed_analytics` against real data -- replace it with your ETL into the analytics DB.
3. **Secrets**: `JWT_SECRET`, DB passwords and provider keys from a secret manager, never baked
   into images. Rotate `JWT_SECRET` to invalidate all tokens.
4. **Scaling**: the API is stateless except for the in-process rate limiter and the cached value
   index. With more than one replica, move rate limiting to a shared store (Redis / gateway) --
   documented limitation.
5. **TLS**: terminate at a load balancer or ingress in front of the web container; set
   `CORS_ORIGINS` to the real origin.
6. **Observability**: logs are JSON on stdout with `request_id`; ship them to your log stack.
   `query_history` and `audit_events` are queryable for usage and security review.
7. **Real data**: point `ANALYTICS_READER_DATABASE_URL` at a read replica, extend
   `app/semantic/layer.py` (metrics, dimensions, joins, allowlist) and re-run the evaluation with
   new expected values.
