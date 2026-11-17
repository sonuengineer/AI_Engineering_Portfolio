# NEXUS AI -- API reference

Base URL (dev): `http://localhost:8101`. Interactive OpenAPI: `http://localhost:8101/api/docs`.
All `/api/v1` endpoints except login require `Authorization: Bearer <token>`.
Errors always use: `{"error": {"code", "message", "request_id", "details?"}}`.

| Method | Path | Min role | Purpose |
|---|---|---|---|
| POST | /api/v1/auth/login | -- | Email/password -> JWT (rate limited per IP) |
| GET | /api/v1/auth/me | viewer | Current user, org, configured providers |
| POST | /api/v1/chat/ask | viewer | Grounded answer with citations |
| GET | /api/v1/conversations | viewer | Own conversations |
| GET | /api/v1/conversations/{id}/messages | owner | Conversation history |
| GET/PUT | /api/v1/memory | viewer | Controlled long-term memory (own items) |
| DELETE | /api/v1/memory/{id} | owner | Delete a memory item |
| GET | /api/v1/documents | viewer | Org documents with ingestion status |
| GET | /api/v1/documents/{id} | viewer | One document |
| GET | /api/v1/documents/{id}/chunks | viewer | Chunks with page/section/flags |
| POST | /api/v1/documents/upload | analyst | Multipart upload -> 202 + queued job |
| POST | /api/v1/documents/url | analyst | SSRF-safe fetch of allowlisted URL |
| DELETE | /api/v1/documents/{id} | manager | Delete document and chunks |
| POST | /api/v1/workflows | analyst | Start investigation (background) -> 202 |
| GET | /api/v1/workflows | viewer | Run history |
| GET | /api/v1/workflows/{id} | viewer | Run, steps, tool calls, report, approvals |
| POST | /api/v1/workflows/{id}/resume | analyst | Resume failed/interrupted run from checkpoint |
| GET | /api/v1/approvals?status= | viewer | Approval queue |
| POST | /api/v1/approvals/{id}/approve | manager | Approve (optionally edit) and execute once |
| POST | /api/v1/approvals/{id}/reject | manager | Reject |
| GET | /api/v1/tools | viewer | Tool registry metadata + JSON schemas |
| GET | /api/v1/admin/usage | manager | Token/cost/latency by purpose |
| GET | /api/v1/admin/audit | manager | Audit trail |
| GET | /api/v1/admin/outbox | manager | Emails delivered by the local connector |
| GET | /api/v1/admin/users | admin | Users in org |
| GET | /healthz, /readyz | -- | Liveness / readiness (DB check) |

## Examples (bash)

```bash
TOKEN=$(curl -s -X POST localhost:8101/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"manager@acme.example","password":"<DEMO_USER_PASSWORD>"}' | jq -r .access_token)

curl -s -X POST localhost:8101/api/v1/chat/ask -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"question":"When did the Ironclad contract expire?"}'
```

Response (abridged, real output from the seeded demo):

```json
{
  "conversation_id": "3e79...",
  "answer": "Based on the indexed documents: [Contract status] The master supply agreement between Acme Industrial Supply and Ironclad Construction expired on 30 June 2026 [1].",
  "citations": [{"ref": 1, "document_title": "Ironclad Construction -- Supply Agreement Summary", "page": null, "chunk_id": "...", "document_id": "...", "snippet": "...", "flagged": false}],
  "contexts": ["..."],
  "insufficient_evidence": false,
  "provider": "local",
  "model": "rule-based-v1",
  "usage": {"input_tokens": 901, "output_tokens": 34, "estimated_cost_usd": 0.0, "tokens_are_estimates": true},
  "latency_ms": 41
}
```

```bash
# Start an investigation, then poll it
RUN=$(curl -s -X POST localhost:8101/api/v1/workflows -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"goal":"Investigate why purchases are declining among our top ten customers"}' | jq -r .id)
curl -s localhost:8101/api/v1/workflows/$RUN -H "Authorization: Bearer $TOKEN" | jq '.status, .steps[].name'

# Approve the first pending draft with an edited subject
APPROVAL=$(curl -s "localhost:8101/api/v1/approvals?status=pending" -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')
curl -s -X POST localhost:8101/api/v1/approvals/$APPROVAL/approve -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"subject":"Quick account review","note":"ok"}'

# Upload a document
curl -s -X POST localhost:8101/api/v1/documents/upload -H "Authorization: Bearer $TOKEN" -F file=@policy.pdf
```

## MCP

`python -m app.mcp_server` (stdio) exposes: search_customers, get_top_customers,
get_customer_orders, search_documents, search_emails, get_pending_quotations, generate_report,
draft_followup_email. Calls run as `NEXUS_MCP_USER_EMAIL` through the same registry (role checks,
validation, audit). `send_email` is never exposed.
