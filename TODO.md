# TODO (next highest-value work)

1. Fill portfolio placeholders: copy portfolio/.env.example to .env.local and set VITE_OWNER_NAME,
   contact links and repo URLs; rebuild (`docker build -f portfolio/Dockerfile -t ai-portfolio .`).
2. Push each project to its own GitHub repository so the three CI workflows actually run.
3. Add an LLM key (GEMINI_API_KEY) and re-run the EvalOps benchmarks with LLM_PROVIDER=gemini for
   NEXUS and DATAWISE; compare against the local-adapter baselines already stored.
4. EvalOps: make groundedness skip expected-abstention cases (documented false failure).
5. DATAWISE: decide the all-time-aggregate policy (clarify vs default to all time) and align the
   benchmark or the planner deliberately.
6. NEXUS: S3 ObjectStorage adapter + OpenTelemetry spans; ingestion lock heartbeat.
7. Deploy one project (NEXUS) to AWS using nexus-ai/docs/deployment.md.
8. Delete the local test account e2e-viewer@evalops.local before any shared deployment.
