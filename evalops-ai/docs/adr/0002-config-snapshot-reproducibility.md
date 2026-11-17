# ADR 0002: Immutable dataset versions + config snapshot per run

Status: accepted (2026-11-16)

## Context
A score is only meaningful if you can say exactly what produced it. Prompts, model params and
datasets are edited over time.

## Decision
Dataset versions are immutable and content-hashed (SHA-256 of canonical JSON). Each run stores a
JSON snapshot of the target, model config, prompt text + hash, evaluator configs, dataset version +
hash, seed, execution params and git sha at creation time. The engine reads only the snapshot.

## Consequences
+ Editing an evaluator or prompt never changes historical runs; comparisons can warn when dataset
  hashes differ.
- Snapshots duplicate data (small) and old runs cannot be "re-scored" by editing configs; you
  create a new run instead.
