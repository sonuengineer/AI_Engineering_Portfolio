# ADR 0002 -- Semantic layer as a typed Python registry

Status: accepted (2026-11-16)

## Context
The semantic layer defines metrics, dimensions, synonyms, join paths and the allowlist. Options:
YAML/JSON files (dbt/Cube style) or a Python module.

## Decision
`app/semantic/layer.py` with frozen dataclasses. Dimensions are bound per fact (sales, web,
deliveries) so the compiler knows which joins a dimension needs and which metric/dimension
combinations are impossible.

## Consequences
+ Type-checked by mypy; no YAML parser or schema-validation layer to maintain.
+ One source of truth for compiler, validator allowlist, catalog endpoint and LLM prompt.
- Business users cannot edit definitions without a code change and deploy. A YAML loader that
  produces the same dataclasses is a straightforward later step if that becomes a need.
