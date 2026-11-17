# NEXUS AI -- Roadmap and known limitations

## Known limitations (current state)
- **Local adapter quality**: extractive answers and keyword-based hypotheses; no negation handling
  ("quality remains good" vs "quality complaint" handled only via specific phrases).
- **Local embeddings are lexical** (feature hashing). Semantic retrieval needs a real embedding
  provider and re-indexing.
- **Gemini/OpenAI adapters are untested live** (no keys in this environment); verified against SDK
  signatures and type checks only.
- **Object storage**: only the local filesystem implementation exists; S3 adapter is designed
  (protocol in `ingestion/storage.py`) but not written.
- **No OCR**: scanned PDFs produce no text and fail ingestion with a clear error.
- **Rate limiting per process**; **no refresh tokens**; JWT in sessionStorage.
- **Single-tenant admin UI**: no user management screens (users are seeded).
- **Workflow types**: only the customer-decline investigation is implemented; the supervisor
  rejects other goals honestly.
- **OpenTelemetry**: request ids and structured logs exist; OTel tracing export is not wired in
  NEXUS (EvalOps implements tracing).
- **Frontend bundle** is not code-split (~700 kB).
- **Not deployed**: deployment guide is a design, not an executed runbook.
- **Token budget projection** counts prompt size before a call but not the upcoming output tokens,
  and failed attempts are not charged; `budget_exceeded` runs cannot be resumed with a raised budget.
- **Ingestion locks are not refreshed**: a job running longer than 10 minutes can be reclaimed by a
  second worker (heartbeat column is the fix).
- **Login rate limiting behind a proxy**: unless uvicorn trusts the proxy (`--forwarded-allow-ips`),
  all clients behind nginx share one per-IP bucket; trusting `*` would allow spoofing when the API
  port is exposed directly. Production: rate-limit at the WAF/ALB.

## Roadmap (priority order)
1. S3 object storage adapter + MinIO in compose.
2. OpenTelemetry spans for retrieval, model and tool calls.
3. Cross-encoder reranker behind the same `rerank` interface.
4. Redis-backed rate limiter and token revocation.
5. More workflow types (quotation follow-up, churn-risk sweep) as additional graphs.
6. LLM-based query rewriting for follow-up questions using conversation history.
7. User/role management UI and SSO (OIDC).
