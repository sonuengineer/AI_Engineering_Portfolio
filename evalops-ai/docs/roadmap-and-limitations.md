# Roadmap and limitations

## Known limitations (current state)

- Gemini/OpenAI providers, LLM judge with a real provider, DeepEval/RAGAS adapters and OTLP export
  are implemented against introspected SDK signatures but were never called live (no keys).
- DeepEval/RAGAS are not uv extras (they conflict with openai 3.51 in one lock); install manually
  into the venv (`uv pip install deepeval==4.3.4` or `ragas==0.4.4`). RAGAS adapter wires only the
  OpenAI client path.
- NEXUS/DATAWISE benchmarks have not been run live from this environment (credentials not provided
  to EvalOps); targets are configured and ready.
- Per-call timeout relies on client timeouts (httpx / SDK); a provider that ignores timeouts can
  hold a worker thread.
- No worker lease/heartbeat; crashed workers leave runs `running`. Only queued runs can be cancelled.
- Rate limiter is per process; login limiter keys on client IP (behind nginx all users share one).
- Lexical RAG metrics are heuristics (see evaluation-methodology.md).
- Token counts/costs for deterministic providers are estimates.
- No trace retention policy, no CSP header, no target URL egress allowlist.
- Docker image does not include optional extras (gemini/openai/otlp).

## Roadmap

1. Worker leases + heartbeat, run cancellation for running runs, retry of failed runs.
2. Judge calibration: agreement with human labels, opt-in gating for calibrated judges.
3. Embedding-based semantic similarity metric as an optional evaluator.
4. Pairwise (A/B) judge comparisons and statistical significance (bootstrap CI) for pass-rate deltas.
5. Trace retention + sampling; OTel GenAI semantic conventions.
6. Per-org quotas, egress allowlist for HTTP targets, CSP.
7. Dataset editing UI with diff between versions.
