# ADR 0003: Deterministic metrics gate; judge metrics are labeled estimates

Status: accepted (2026-11-16)

## Context
LLM-as-judge scores are noisy, provider-dependent and can be manipulated by the evaluated text.
Mixing them into pass/fail makes CI flaky and hard to explain.

## Decision
Evaluators have `kind` deterministic|judge. Judge scores are always `is_estimate=true`, shown with
an "estimate" badge, reported in comparisons, and excluded from case pass/fail and the CI gate. The
API forces `gating=false` for judge evaluators. With a deterministic provider the judge refuses
(status skipped) instead of producing a fake score.

## Consequences
+ CI gate results are reproducible and explainable.
- Semantic quality not captured by deterministic metrics is only advisory until a team chooses to
  trust a calibrated judge (future: opt-in gating with agreement checks).
