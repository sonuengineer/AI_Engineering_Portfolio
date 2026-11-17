# ADR 0001 -- The planner emits a typed QueryPlan, never SQL

Status: accepted (2026-11-16)

## Context
Text-to-SQL systems that execute model-written SQL rely on the model never producing something
harmful or wrong (injection, writes, cross-table leaks, hallucinated joins). Validating free-form
SQL after the fact is possible but brittle.

## Decision
Every planner (local rules, Gemini, OpenAI) returns a `PlannerOutcome` containing a Pydantic
`QueryPlan` (metrics, dimensions, typed filters, time range, order, limit) with `extra="forbid"`.
SQL is produced exclusively by `app/services/compiler.py` from the semantic layer.

## Consequences
+ Model output cannot contain SQL; identifiers come from our registry; values are escaped literals.
+ Plans are inspectable, savable (saved reports) and re-runnable without a model.
+ Same compiler/validator/executor path for every provider -> comparable evaluations.
- Expressiveness is limited to what the semantic layer models (no arbitrary subqueries, window
  functions, cohort analysis). New analyses require extending the registry.
