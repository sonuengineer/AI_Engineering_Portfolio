# NEXUS AI -- Security and threat model

## Assets
Customer and order data, documents, emails, approval decisions, credentials (JWT secret, LLM keys),
and the ability to send email on the company's behalf.

## Trust boundaries
1. Browser <-> API (untrusted client).
2. API <-> uploaded/fetched documents and email bodies (untrusted content that reaches prompts).
3. API <-> LLM provider (model output is untrusted until validated).
4. Tenant A <-> tenant B data inside one database.
5. MCP clients <-> tool registry.

## Threats and controls (STRIDE-style)

| Threat | Control | Where | Tested |
|---|---|---|---|
| Credential stuffing / brute force / account enumeration | Per-IP login rate limit, generic error, dummy-hash verification for unknown emails (no timing oracle), audit of failures | api/auth.py | test_login_failure_is_generic_and_audited |
| Token forgery / alg confusion | HS256 only, required exp/sub, `typ=access`, user+org re-checked on every request | core/security.py, api/deps.py | test_jwt_roundtrip_and_tamper |
| Weak secrets in prod | Settings refuse placeholder/short JWT_SECRET when APP_ENV=production | core/config.py | test_production_settings_reject_weak_secret |
| Cross-tenant read | `org_id` filter in every query, retrieval and tools; 404 (not 403) on foreign ids | services, connectors, retrieval | test_tenant_isolation_*, test_cross_tenant_cannot_see_run_or_approvals, test_retrieval_is_tenant_scoped |
| Privilege escalation | Role ranks enforced in route deps and inside the tool registry | api/deps.py, tools/registry.py | test_admin_endpoints_require_roles, test_analyst_cannot_approve |
| Prompt injection in documents | Scanner flags, untrusted envelopes, system rules, citation/source validation, approval gate | ingestion/injection.py, services/chat.py, agents/investigation.py | test_injection_scanner_*, test_flagged_injection_document_visible_but_marked, test_ground_sources_* |
| Agent performs unwanted external action | `send_email` requires approval record + manager role; not exposed via MCP | tools/builtin.py, services/approvals.py | test_send_email_tool_blocked_without_approval, test_mcp_exposes_read_tools_but_never_send_email |
| Duplicate sends on retry/double click | Idempotency keys (unique constraints) + row lock on approval | models/workflows.py, services/approvals.py | test_approve_sends_once_idempotently_and_reject |
| Hallucinated citations / sources | `validate_citations`, `ground_sources` | services/chat.py, agents/investigation.py | test_citation_validation_*, test_ground_sources_* |
| Malicious uploads | Size cap with bounded read, extension allowlist, magic bytes, zip-bomb ratio, macro rejection, UTF-8 check | ingestion/validation.py, api/documents.py | test_rejects_* |
| SSRF via URL ingestion | Scheme check, host allowlist, no literal IPs, DNS -> public-only, manual redirects re-validated, size + content-type limits | ingestion/ssrf.py | test_ssrf.py (13 cases) |
| XSS via report/document text | React renders text nodes only; Markdown component never uses innerHTML; nginx CSP | frontend/src/components/Markdown.tsx | Markdown test in components.test.tsx |
| Path traversal in storage | Content-addressed keys, resolved-path containment check | ingestion/storage.py | -- |
| Cost exhaustion | Per-run token budget, per-user rate limit, request size limits | agents/runtime.py | test_budget_exceeded |
| Sensitive data in logs | Structured logs omit prompts/bodies; redaction processor masks secret-like keys and values | core/logging.py | -- |
| Repudiation | Audit events for logins, tool calls (denied/blocked ones in an independent transaction so they survive rollback), approvals, uploads, memory changes, with request ids | services/audit.py | test_login_failure_is_generic_and_audited, test_denied_tool_call_audit_survives_rollback |

## Known gaps (honest list)
- DNS rebinding: resolution check and connection are separate (documented in ssrf.py); production
  should use an egress proxy.
- Rate limiting is per process (no shared store).
- JWT in sessionStorage is readable by injected scripts; CSP mitigates XSS but httpOnly-cookie
  sessions with CSRF protection would be stronger.
- No refresh tokens / revocation list; tokens live until expiry (60 min default).
- Prompt-injection scanner is heuristic (regex); novel attacks will pass it, which is why output
  validation and human approval exist.
- No malware/AV scanning of uploads; PDFs are parsed by pypdf in-process (consider sandboxing).
- Emails and documents are stored unencrypted at the application layer (rely on disk/RDS/S3
  encryption at rest).
