# Security threat model

Scope: the question pipeline, auth, multi-tenancy and the database boundary. Method: STRIDE-style
list of threats, the controls in place, and residual risk.

## Assets

- Analytics data (business data; read-only for users)
- App data: user accounts and password hashes, other orgs' history and saved reports, audit log
- Database availability (expensive queries)
- Provider API keys (when LLM providers are enabled)

## Trust boundaries

1. Browser -> API (untrusted input: question text, plan JSON in saved reports, JWT)
2. API -> LLM provider (untrusted output: model JSON)
3. API -> analytics DB (must be read-only, allowlisted)
4. API -> app DB (tenant isolation)

## Threats and controls

| # | Threat | Controls | Tests |
|---|---|---|---|
| T1 | SQL injection / arbitrary SQL via question or model output | Planner can only produce a typed `QueryPlan` (`extra="forbid"`, no SQL field); compiler builds SQL from registry identifiers; values escaped by sqlglot literal rendering | `test_compiler.py::test_string_literals_are_escaped`, `test_plan_rejects_extra_fields_like_raw_sql` |
| T2 | Data modification (DML/DDL) | Guardrails reject write intent; validator rejects any DML/DDL/COPY/SET/SELECT INTO/FOR UPDATE/CTE-DML node; reader role has SELECT only and `default_transaction_read_only=on`; executor sets READ ONLY | `test_validator.py` (45 cases), `test_executor.py` (writes fail even inside `SET TRANSACTION READ WRITE`) |
| T3 | Reading credentials / users / system catalogs | Users live in a different database the reader cannot CONNECT to; validator table/column/schema allowlist; guardrails reject requests for passwords, users, pg_catalog, information_schema | `test_reader_cannot_connect_to_app_db`, validator cases for pg_catalog/pg_shadow/information_schema/users |
| T4 | Prompt injection ("ignore previous instructions") | Guardrail rejects before the planner; even if bypassed, the model can only emit a plan that is validated against the semantic layer | `test_planner.py::test_guardrails_reject` |
| T5 | Denial of service via expensive queries | `SET LOCAL statement_timeout` (5 s default) plus role-level 10 s; `LIMIT <= MAX_ROWS` enforced by compiler and validator; `fetchmany(MAX_ROWS+1)`; functions allowlist blocks `pg_sleep`; per-user rate limit on ask/run | `test_statement_timeout`, `test_row_cap_applies_even_without_limit`, `test_rate_limit` |
| T6 | Cross-tenant access to history/reports | `org_id` filter on every query; reports return 404 (not 403) for other orgs | `test_history_is_tenant_isolated`, `test_saved_reports_crud_rerun_and_isolation` |
| T7 | Stolen/forged token | HS256 JWT with `exp`, `sub`, `org`; org claim must match the user's org; short lifetime (60 min) | `test_auth_required` |
| T8 | Password cracking | argon2 (argon2-cffi defaults); generic "Invalid email or password"; failed logins audited | `test_login_bad_password_uses_error_envelope` |
| T9 | Fabricated numbers in answers | Insight computed only from returned rows with provenance; no model writes insight text | `test_insight.py` compares with independent SQL |
| T10 | Secrets in logs | structlog events log ids, statuses, latencies -- never questions' tokens, passwords or prompts; unhandled errors log only the exception type | code review |
| T11 | Tampered saved-report plan | Plan is re-validated by Pydantic + `compile_plan` on save and on every run, then the normal validator/executor path | `test_saved_report_rejects_invalid_plan` |

## Residual risks and known gaps

- **Guardrails are pattern-based** and can false-positive (e.g. the word "update" in a business
  question) or miss creative phrasings. They are a UX layer; T1-T3 do not depend on them.
- **sqlglot vs Postgres parser differences**: the validator could in theory accept SQL that
  Postgres interprets differently. Mitigated because the SQL is produced by our compiler and the
  role is read-only; the validator is defense in depth, not the only control.
- **Reader can read pg_catalog** (Postgres grants catalog visibility to all roles). Only reachable
  if the validator is bypassed; exposes schema metadata, not app data.
- **Analytics data is shared across orgs** in this demo (one synthetic company). A real multi-tenant
  deployment needs per-tenant analytics databases or row-level security keyed on the org.
- **JWT in localStorage** in the SPA: vulnerable to XSS token theft. The SPA renders no HTML from
  data (React escaping); an httpOnly cookie + CSRF protection would be the hardening step.
- **Rate limiter is in-process**: not shared across replicas.
- **No account lockout**; brute force is slowed only by argon2 cost and the absence of user
  enumeration.
- **LLM providers untested live**: the repair loop and schema handling are unit-checked only via
  the shared parse function, not against real APIs.
