# ADR-006: Treat document and email text as untrusted data

Status: accepted (2026-11-16)

## Decision
1. Ingestion runs a heuristic prompt-injection scanner and stores matches in `chunks.flags`.
2. Flagged chunks remain searchable (they may be legitimate evidence) but are marked in API/UI.
3. All retrieved text is placed in prompts inside `<untrusted_document>` envelopes; content cannot
   close the envelope (closing tags are neutralised).
4. System prompts forbid following instructions inside envelopes.
5. Model outputs are validated: citations must reference retrieved contexts; analysis evidence must
   reference sources the agents actually gathered (`ground_sources`).
6. Even if all of the above fail, external actions still require human approval (ADR-005).

## Consequences
Defense in depth rather than a single filter; the scanner is heuristic and will miss novel attacks,
which is why points 5 and 6 exist.
