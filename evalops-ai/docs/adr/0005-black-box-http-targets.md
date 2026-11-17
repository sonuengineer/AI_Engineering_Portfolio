# ADR 0005: Benchmark sibling apps as black-box HTTP targets

Status: accepted (2026-11-16)

## Context
NEXUS AI and DATAWISE AI are separate products. Importing their code would couple deployments.

## Decision
EvalOps calls only their documented HTTP contracts (MASTER_ARCHITECTURE.md section 3). Credentials
are resolved from env vars named in the target config. NEXUS citations are matched on
`document_title` because `document_id` values are regenerated on every NEXUS seed. DATAWISE expected
rows are computed offline from its seeded data generator by a build script, not by calling its code
at runtime.

## Consequences
+ Independent deployability; the same benchmark works against any environment.
- Benchmarks must be regenerated when a sibling corpus/generator changes; title-based citation
  matching breaks if titles change.
