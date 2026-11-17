# ADR 0004 -- Deterministic local planner as the default provider

Status: accepted (2026-11-16)

## Context
No LLM API keys are available for development, CI or demos, and fake "LLM" output would be
dishonest.

## Decision
`LLM_PROVIDER=local` (default) is a rule-based planner: time-phrase parser, longest-match synonym
scanner, grouping-cue detection, fact-aware value disambiguation and explicit clarification rules.
It is labeled `provider="local"` / `model="rules-v1"` in every response and with a
"Deterministic local adapter" badge in the UI. Gemini and OpenAI providers implement the same
interface with JSON-schema structured output and one repair retry.

## Consequences
+ Demos, tests and the eval gate run offline, free and reproducibly (latency ~20-40 ms).
+ Clarification behaviour is predictable and testable.
- Limited language coverage: 50% on the held-out paraphrase set (see evaluation.md). Unsupported
  phrasings fail safe (clarification), but users must phrase questions in supported ways.
