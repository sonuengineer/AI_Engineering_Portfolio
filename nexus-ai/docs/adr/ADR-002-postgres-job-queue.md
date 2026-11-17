# ADR-002: Postgres SKIP LOCKED queue for ingestion instead of Celery/ARQ + Redis

Status: accepted (2026-11-16)

## Context
Ingestion must run in the background, survive crashes, and allow multiple workers.

## Decision
Use an `ingestion_jobs` table claimed with `SELECT ... FOR UPDATE SKIP LOCKED`. Jobs are enqueued
in the same transaction that creates the document. Stale `processing` jobs (lock older than 10
minutes) are reclaimed. Retries are bounded by `max_attempts`; `ValueError`s (bad content) fail
immediately.

## Consequences
+ One fewer service; transactional enqueue (no lost or orphan jobs); easy to inspect with SQL.
+ Horizontally scalable workers (`python -m app.worker`, N replicas).
- Polling adds up to 1 s latency; heavy throughput would favour a broker (SQS/Redis streams).
- No scheduled/periodic jobs or priorities yet.
