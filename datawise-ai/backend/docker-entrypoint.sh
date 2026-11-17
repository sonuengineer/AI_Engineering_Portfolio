#!/bin/sh
# Optional one-shot bootstrap (compose sets RUN_MIGRATIONS_AND_SEED=1): migrations + demo users +
# analytics seed (skipped if already seeded). All steps are idempotent.
set -eu
if [ "${RUN_MIGRATIONS_AND_SEED:-0}" = "1" ]; then
  alembic upgrade head
  python -m scripts.seed
  python -m scripts.seed_analytics
fi
exec "$@"
