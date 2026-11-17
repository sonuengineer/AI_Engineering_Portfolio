# ADR-001: Deterministic local adapter instead of fake LLM output

Status: accepted (2026-11-16)

## Context
The platform must be demoable and testable without paid API keys, but must never pretend a model
call happened.

## Decision
`LLM_PROVIDER=local` selects `app/llm/local.py`, a rule-based implementation of each task
(`answer_question`, `plan_workflow`, `analyze_evidence`, `draft_email`) that works on the same
structured payload a real provider receives as a prompt. Every response is tagged `provider=local`,
token counts are flagged as estimates, cost is 0, and the UI shows a "Deterministic local adapter"
badge. Gemini and OpenAI adapters implement the same `LLMProvider` protocol.

## Consequences
+ Tests exercise the full pipeline (retrieval, validation, agents, approvals) deterministically.
+ Demo works offline.
- Local answers are extractive and keyword-based: weaker reasoning, no negation handling.
- Gemini/OpenAI adapters are not exercised in CI (no keys); they are verified against SDK
  signatures only.
