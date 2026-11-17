# ADR 0004: Deterministic `local` and `mock_scripted` providers for keyless demos and CI

Status: accepted (2026-11-16)

## Context
The platform must run, demo and gate in CI without paid API keys, without pretending a rule-based
adapter is an LLM, and without inventing benchmark numbers.

## Decision
Two non-LLM providers behind the same interface: `local` (rule-based extractive / echo) and
`mock_scripted` (replays outputs scripted in the dataset under `metadata.scripted_outputs[script]`).
Runs using them carry `is_deterministic_provider=true` and the UI/report show a "not a real LLM"
banner. The CI eval-gate runs scripted targets; a deliberately regressed script (v2) proves the gate
blocks regressions.

## Consequences
+ Honest, reproducible demos and a working CI gate with zero secrets.
- Scores for these runs measure the adapter/fixtures, not model quality; that is stated everywhere.
