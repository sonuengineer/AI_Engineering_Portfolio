# ADR 0003 -- Validator plus read-only role (defense in depth)

Status: accepted (2026-11-16)

## Context
Even with our own compiler, bugs or future features could generate unsafe SQL.

## Decision
Three independent layers after compilation:
1. sqlglot validator (postgres dialect): exactly one SELECT; no DML/DDL/COPY/SET/INTO/LOCK nodes
   anywhere in the tree; table, column, schema and function allowlists; outer `LIMIT <= MAX_ROWS`.
2. Executor: `SET TRANSACTION READ ONLY`, `SET LOCAL statement_timeout`, `fetchmany(MAX_ROWS+1)`,
   always rolls back.
3. Database role `datawise_reader`: CONNECT only on the analytics DB, SELECT only,
   `default_transaction_read_only=on`, role-level statement timeout; cannot connect to the app DB.

## Consequences
+ A failure in any single layer does not allow writes or reading user data (tests prove the role
  alone blocks writes even inside `SET TRANSACTION READ WRITE`).
- Function allowlist must be extended when the compiler gains new SQL features (caught by
  `test_every_metric_dimension_combination_compiles_and_validates`).
