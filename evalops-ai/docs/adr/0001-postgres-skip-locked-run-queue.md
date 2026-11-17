# ADR 0001: Postgres SKIP LOCKED table as the run queue

Status: accepted (2026-11-16)

## Context
Runs take seconds to minutes and must not block HTTP requests. Options: Celery/RQ + Redis, a cloud
queue, or the `runs` table itself.

## Decision
Use the `runs` table as the queue: workers claim with
`UPDATE runs SET status='running' WHERE id = (SELECT id ... WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING id`.
The worker is embedded in the API in dev and a separate container in compose.

## Consequences
+ No extra infrastructure; run state and queue state cannot diverge; tested that two claims never
  return the same run.
- No lease/heartbeat: a crashed worker leaves a run `running` forever (roadmap).
- Polling latency (1 s default) instead of push.
