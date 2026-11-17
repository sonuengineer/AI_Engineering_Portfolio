# ADR-004: LangGraph orchestration with our own per-step checkpoints

Status: accepted (2026-11-16)

## Context
Investigations are multi-step, may call slow tools/models, and must be resumable and auditable.

## Decision
Use LangGraph `StateGraph` for routing (supervisor plan -> conditional edges) and wrap every node
in `agents/runtime.run_step`, which persists step status/output/tool calls in `workflow_steps`,
merges state into `workflow_runs.state`, enforces timeouts (thread + rollback-on-timeout), retries
transient errors, and enforces the token budget.

## Alternatives considered
- LangGraph's Postgres checkpointer: stores opaque serialized graph state; we wanted queryable,
  UI-friendly step records and a business-level audit trail.
- A hand-written state machine: loses LangGraph's conditional routing and visualization.

## Consequences
+ Agent activity UI and resume come straight from relational rows.
- Two notions of state (graph state in memory, checkpoint in DB) must be kept in sync by `run_step`.
- Python threads cannot be killed: a timed-out attempt may keep running briefly, but its writes are
  rolled back.
