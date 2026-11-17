# NEXUS AI -- Testing strategy and actual results

## Strategy
- **Real dependencies**: tests run against a real PostgreSQL 17 + pgvector database (`nexus_test`),
  migrated with Alembic and seeded with the same seed script as the demo.
- **Mocks only at external boundaries**: DNS resolution and HTTP transport in SSRF tests
  (`httpx.MockTransport`), and `fetch` in two frontend component tests. Retrieval, agents, tools,
  approvals, and the API all run for real. The LLM is the deterministic `local` provider, a real
  implementation of the provider interface rather than a mock.
- **Failure injection**: workflow tests monkeypatch one agent to raise (transient or
  non-retryable) to verify retry, failure status and resume-from-checkpoint.
- **E2E**: Playwright drives the real UI against the running API.

## Suites

| Suite | Files | Focus |
|---|---|---|
| Unit | test_ingestion_unit.py, test_ssrf.py, test_security_unit.py, test_llm_local.py | validation, extraction, chunking, injection scanner, SSRF, JWT, rate limit, settings, local LLM, citation/source grounding |
| Integration | test_api_integration.py, test_workflow_integration.py, test_retrieval_and_mcp.py | API contract, auth, tenancy, uploads, memory, investigations, approvals, idempotency, budgets, retries, resume, MCP |
| Frontend | src/components/components.test.tsx | safe markdown, provider badge, role-gated approval UI |
| E2E | frontend/e2e/demo.spec.ts | Q&A + abstention, investigation -> approval -> outbox, documents, viewer restrictions |

## Results (run on 2026-11-16, Windows 11, Docker Postgres)

```
backend:   uv run pytest            -> 88 passed in ~17s
lint:      ruff check + ruff format --check  -> clean
types:     mypy app (58 files)      -> Success: no issues found
frontend:  npx vitest run           -> 4 passed
build:     tsc -b && vite build     -> success (bundle ~700 kB minified; code-splitting not done)
e2e:       npx playwright test      -> 4 passed (against live API + Vite, seeded data)
docker:    docker compose --profile full up --build -> api, worker, web, db all healthy;
           e2e re-run against nginx build (E2E_BASE_URL=http://localhost:8081) -> 4 passed;
           upload processed by the separate worker container -> status ready
```

Bugs found by these tests or by the e2e run and then fixed:
1. The local answerer cited off-topic sentences and answered "What is the capital of France?" from
   "capital expenditure". Fixed with a coverage threshold plus an abstention test.
2. The research agent attached a whole multi-customer spreadsheet chunk to every customer,
   creating false "delivery" hypotheses. Fixed with per-customer excerpts and regression test
   `test_shared_documents_do_not_create_false_hypotheses`.
3. Testing Library cleanup did not run without vitest globals. Fixed in test-setup.ts.
4. Found while writing the interview handbook (code review), fixed with regression tests:
   - startup recovery marked EVERY running workflow as interrupted, breaking runs owned by other API
     replicas during a rolling deploy -> only runs without step activity beyond the retry budget
     (`test_startup_recovery_only_marks_stale_runs`);
   - denied/blocked tool-call audit rows were lost when the request rolled back -> written in an
     independent transaction (`test_denied_tool_call_audit_survives_rollback`);
   - login skipped password hashing for unknown emails (timing oracle) -> verifies against a dummy hash;
   - deleting a document left its stored file -> object deleted after commit
     (`test_delete_document_removes_stored_object`).
