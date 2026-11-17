# Testing

All backend tests run against the REAL compose Postgres (no DB mocks). `tests/conftest.py` applies
Alembic migrations, seeds demo users and seeds analytics (if empty) at session start, so the suite
also works on an empty database (CI).

## Commands

```bash
docker compose up -d db                 # Postgres on 5442
cd backend
uv run pytest -q                        # backend tests (testpaths = ../tests)
uv run ruff check . ../tests ../evaluation
uv run mypy app scripts
uv run pip-audit

cd ../frontend
npm run typecheck && npm test && npm run build
```

## Actual results (2026-11-16, Windows 11, Python 3.12.14, Node 24.21.0)

```
backend:  149 passed in 6.89s           (pytest 9.2.0)
  test_validator.py   45   malicious SQL (DML/DDL, multi-statement, CTE-DELETE, SELECT INTO,
                           FOR UPDATE, pg_sleep/pg_read_file/dblink/lo_import/set_config,
                           pg_catalog/pg_shadow/information_schema/users, SELECT *, missing or
                           oversized LIMIT, OFFSET, EXPLAIN/VACUUM/CALL/DO) + safe queries
  test_planner.py     40   plans, 8 clarification cases, clarification options re-askable,
                           17 guardrail rejections, 5 false-positive checks
  test_timeparse.py   17   relative/absolute periods anchored to 2026-10-31
  test_api.py         15   login/me/errors, ask answered/clarify/rejected, contract keys,
                           tenant isolation of history and reports, report CRUD + re-run,
                           catalog, rate limit, request id
  test_compiler.py    13   cancelled exclusion, join order, literal escaping, LIMIT clamp,
                           HAVING, invalid plans, every metric x dimension compiles + validates
  test_executor.py    12   reader role: writes blocked (also with SET TRANSACTION READ WRITE),
                           read-only default, cannot connect to app DB, timeout, row cap
  test_insight.py      6   numbers equal independent SQL; % change and totals from rows;
                           honest empty result
ruff:     All checks passed!
mypy:     Success: no issues found in 42 source files
pip-audit: No known vulnerabilities found

frontend: Test Files 3 passed (3), Tests 8 passed (8)   (vitest 4.1.12)
  AnswerPanel.test.tsx  badge, SQL + copy button, validation issues, insight, clarification
                        buttons call back with the option, rejection rendering
  chart.test.ts         time-series mapping, series pivot, value formatting
  Login.test.tsx        API error message shown on bad credentials
tsc --noEmit: clean;  vite build: OK;  npm audit --omit=dev: 0 vulnerabilities
```

## End-to-end checks performed manually

- `docker compose up -d --build` from an EMPTY volume: migrations, seeds, healthcheck healthy;
  login and ask through nginx on :5172 returned `answered`.
- Evaluation run against that stack (see evaluation.md).
- Vite dev server on :5172 proxied `/api` to the dev API (login verified with curl).
- NOT done: visual inspection of the UI in a browser (no browser automation was available in the
  build environment). Component behaviour is covered by the vitest tests above.

## Fixes made after code review (interview-handbook pass, 2026-11-16)
- Rate-limit bypass: buckets were keyed by the concrete URL path, giving every saved report its own
  30/min budget. Now one per-user bucket covers all query-executing endpoints
  (`test_rate_limit_is_shared_across_query_endpoints`).
- Login timing oracle: unknown emails skipped argon2 verification; they now verify against a dummy
  hash so both paths cost the same.
- Browser e2e added: `frontend/e2e/demo.spec.ts` (Playwright) -- answered / clarification / rejected
  flows against the Docker stack: 3 passed. Screenshots in `docs/screenshots/`.
