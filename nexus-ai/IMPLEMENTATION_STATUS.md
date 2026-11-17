# NEXUS AI -- Implementation status

Last updated: 2026-11-16

## Done (verified)
- Backend: models (18 tables), Alembic migration, seed (41 customers, 2901 orders, 49 emails, 12 docs incl. PDF/DOCX/XLSX).
- Ingestion: validation, extraction, chunking, injection scan, SSRF-safe URL fetch, SKIP LOCKED queue, worker.
- Retrieval: pgvector + FTS + RRF + rerank; chat with citation validation, abstention, history, memory.
- Agents: LangGraph supervisor + 5 agents, checkpointed steps, timeout, retry, resume, budgets.
- Tools: typed registry, RBAC, approval gate, idempotent outbox; MCP server (mcp 2.x MCPServer).
- API: auth, chat, documents, workflows, approvals, admin, health; request ids; JSON errors; rate limits.
- Frontend: Login, Ask, Investigations, Run detail, Approvals, Documents, Admin.
- Tests: 97 pytest, 4 vitest, 4 Playwright e2e (dev and Docker stack). ruff + mypy clean.
- Docker: api/worker/web images, compose `--profile full` verified healthy.
- CI: .github/workflows/nexus-ci.yml (not executed on GitHub; no remote).
- Docs: architecture, ER, sequences, API, env, setup, deployment, security, testing, eval, 6 ADRs, roadmap.
- Latency benchmark: docs/benchmarks/latency.json (real measurement).

## Pending
- Interview handbook (generated after all projects are implemented).
- S3 storage adapter, OTel tracing, refresh tokens (see docs/roadmap-and-limitations.md).
