# TODO (next highest-value work)

1. Fill portfolio placeholders: copy portfolio/.env.example to .env.local and set VITE_OWNER_NAME,
   contact links and repo URLs; rebuild (`docker build -f portfolio/Dockerfile -t ai-portfolio .`).
2. Push each project to its own GitHub repository so the three CI workflows actually run.
3. Add an LLM key (GEMINI_API_KEY) and re-run the EvalOps benchmarks with LLM_PROVIDER=gemini for
   NEXUS and DATAWISE; compare against the local-adapter baselines already stored.
4. (done 2026-11-17) EvalOps groundedness skips correct refusals; DATAWISE defaults bare totals to all time;
   NEXUS S3 adapter, OpenTelemetry spans and ingestion heartbeat implemented.
5. Remaining engineering: fencing token for ingestion jobs; streaming/multipart S3; run S3Storage against
   real AWS and OTel against a real collector; context_precision that is top-k aware.
7. Deploy one project (NEXUS) to AWS using nexus-ai/docs/deployment.md.
8. (done) Local e2e test account was deleted; re-create it only when running EvalOps e2e.
