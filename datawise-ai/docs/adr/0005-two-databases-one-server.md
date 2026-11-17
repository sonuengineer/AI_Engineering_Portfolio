# ADR 0005 -- Separate app and analytics databases on one Postgres server

Status: accepted (2026-11-16)

## Context
User accounts, history and audit data must never be reachable by generated queries, while the
demo should stay a single `docker compose up`.

## Decision
One Postgres 17 server, two databases: `datawise_app` (SQLAlchemy + Alembic, accessed by the app
user) and `datawise_analytics` (accessed by requests only through `datawise_reader`). Postgres
does not allow cross-database queries, so even a fully compromised query on the reader
connection cannot touch app tables.

## Consequences
+ Strong isolation with zero extra infrastructure; mirrors a production setup where analytics is a
  read replica or warehouse.
- Two connection strings to manage; analytics schema is created by a seed script rather than
  Alembic (it represents an external data source in real deployments).
