# ADR-005: Side-effecting tools require a human approval record

Status: accepted (2026-11-16)

## Decision
Tools declare `side_effect` (`read|write|external`) and `requires_approval`. Agents can only call
`draft_followup_email`, which creates an `approval_requests` row with an idempotency key. The
`send_email` tool refuses to run without `approved_action_id`, is restricted to managers, and is
never exposed via MCP. Approval locks the row (`FOR UPDATE`) and sends through the outbox with the
same idempotency key, so double-clicks or retries never send twice.

## Consequences
+ An agent compromised by prompt injection cannot send email by itself.
+ Approvers can edit subject/body before sending; the edit is what gets sent and audited.
- Adds latency to workflows (runs end in `awaiting_approval`).
