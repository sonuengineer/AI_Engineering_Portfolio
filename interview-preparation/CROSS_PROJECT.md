# Cross-project interview handbook: NEXUS, DATAWISE, EVALOPS

_Source: Source code of all three projects inspected on 2026-11-16_

## Contents

| Topic | Questions |
|---|---|
| [Portfolio story and positioning](#portfolio-story) | 5 |
| [LLM provider abstraction across projects](#llm-abstraction) | 4 |
| [Safety patterns: grounding, validation, approvals](#safety-patterns) | 5 |
| [Data architecture and multi-tenancy](#data-architecture) | 3 |
| [Closing the loop: evaluating NEXUS and DATAWISE with EVALOPS](#evaluation-loop) | 5 |
| [Operations, delivery and cost](#ops-delivery) | 4 |
| [End-to-end system design and trade-offs](#system-design) | 6 |

Difficulty mix: beginner 3, intermediate 13, advanced 10, senior 6

Labels: `[impl]` = implemented in this repo, `[ext]` = proposed extension (not implemented).

<a id="portfolio-story"></a>
## Portfolio story and positioning

### x001. Give a 60-second overview of the three projects and how they relate.

`beginner` `[impl]`

**Answer.** NEXUS answers questions over enterprise documents with citations and runs a LangGraph multi-agent investigation over CRM/ERP/email data whose outbound emails need human approval. DATAWISE turns business questions into a typed query plan, compiles it to SQL with our own code, validates it with sqlglot and runs it under a read-only role. EVALOPS evaluates LLM systems, including NEXUS and DATAWISE through their HTTP contracts, with deterministic metrics, labeled judge estimates, regression detection and a CI gate. Together they cover the three hard parts of applied LLM work: retrieval and agents, safe data access, and measuring quality.

**Why it matters.** Interviewers want a crisp narrative with a unifying theme (trustworthy LLM systems), not a feature list.

**Code:** `MASTER_ARCHITECTURE.md`, `README.md`

**Follow-ups:**
- Which project was hardest and why?
- What would you build next?

### x002. What single design principle is shared by all three projects?

`beginner` `[impl]`

**Answer.** Never trust model output without a deterministic check. NEXUS validates citations against retrieved contexts and grounds analysis sources against what agents actually gathered; DATAWISE never executes model-written SQL and re-validates the SQL its own compiler produced; EVALOPS separates deterministic metrics from LLM-judge estimates and labels the latter. The model proposes, code verifies, and for side effects a human approves.

**Why it matters.** Tests whether the candidate can abstract a principle from implementations.

**Code:** `nexus-ai/backend/app/services/chat.py:validate_citations`, `datawise-ai/backend/app/services/validator.py:validate_sql`, `evalops-ai/backend/app/evaluators/judge.py:llm_judge`

**Follow-ups:**
- Where does that principle cost you capability?
- How do you explain it to a product manager?

### x003. Why are the projects separate deployables instead of one app with shared libraries?

`intermediate` `[impl]`

**Answer.** Each product has a different risk profile and scaling shape: NEXUS is write-heavy on ingestion and runs long agent workflows, DATAWISE is latency-sensitive and must isolate a read-only analytics connection, EVALOPS runs batch jobs and CI gates. Separate projects keep dependencies, migrations and release cadence independent. The cost is duplicated plumbing (config, auth, logging), accepted deliberately; the only coupling is the HTTP contracts documented in MASTER_ARCHITECTURE.md.

**Why it matters.** Probes judgment about shared code versus coupling.

**Code:** `MASTER_ARCHITECTURE.md`, `nexus-ai/backend/app/core/config.py`, `datawise-ai/backend/app/core/config.py`, `evalops-ai/backend/app/core/config.py`

**Follow-ups:**
- When would you extract a shared library?
- How would you version the HTTP contracts?

### x004. How did you keep the demos honest without paid API keys?

`intermediate` `[impl]`

**Answer.** Every project ships a deterministic local adapter behind the same provider interface as Gemini/OpenAI. Responses carry provider=local, token counts are flagged as estimates, cost is 0 and the UI shows a 'Deterministic local adapter' badge. Tests and demos run the full pipeline (retrieval, validation, agents, SQL execution, evaluation) for real while being explicit that no live model was called.

**Why it matters.** Integrity question: faking AI output in demos is a red flag.

**Code:** `nexus-ai/backend/app/llm/local.py:LocalProvider`, `datawise-ai/backend/app/llm/local.py:LocalPlanner`, `evalops-ai/backend/app/llm/local.py`

**Follow-ups:**
- What does the local adapter NOT prove?
- How would you demo with a real model safely?

### x005. What do these projects NOT prove about your skills, and how would you close the gap?

`advanced` `[impl]`

**Answer.** They do not prove live-model prompt quality, because the Gemini/OpenAI adapters were never exercised with keys; nor cloud operations, because nothing was deployed; nor scale beyond a laptop dataset. To close the gaps: run the EVALOPS benchmarks against a real provider and publish the artifacts, deploy one project to ECS/RDS using the documented topology, and load-test retrieval at millions of chunks.

**Why it matters.** Senior candidates name their own limitations precisely.

**Code:** `nexus-ai/docs/roadmap-and-limitations.md`, `datawise-ai/docs/roadmap-and-limitations.md`

**Follow-ups:**
- Which gap is riskiest for a production hire?
- How long would closing it take?

<a id="llm-abstraction"></a>
## LLM provider abstraction across projects

### x006. Compare the provider abstractions in NEXUS and DATAWISE.

`intermediate` `[impl]`

**Answer.** NEXUS has a generic LLMProvider protocol with generate(request, schema) used for several tasks (answer_question, plan_workflow, analyze_evidence, draft_email); the local provider dispatches on the task name. DATAWISE has a narrower PlannerProvider whose only job is producing a PlannerOutcome (a QueryPlan or a Clarification). The narrow interface is easier to test and harder to misuse; NEXUS needed the general one because many agents call models.

**Why it matters.** Checks understanding of interface width as a design choice.

**Code:** `nexus-ai/backend/app/llm/base.py:LLMProvider`, `datawise-ai/backend/app/llm/base.py:PlannerProvider`, `datawise-ai/backend/app/schemas/plan.py:PlannerOutcome`

**Follow-ups:**
- Would you unify them?
- How would you add streaming?

### x007. How are structured outputs enforced, and what happens when a model returns invalid JSON?

`intermediate` `[impl]`

**Answer.** Both projects pass a JSON schema derived from Pydantic models to the provider (Gemini response_json_schema, OpenAI json_schema response_format) and then validate the reply with Pydantic. In NEXUS remote.py an invalid reply triggers one repair retry that includes the validation error, then a typed StructuredOutputError. Downstream code only ever sees validated objects.

**Why it matters.** Probes knowledge that schema-constrained decoding is not a guarantee.

**Code:** `nexus-ai/backend/app/llm/remote.py:GeminiProvider`, `datawise-ai/backend/app/llm/structured.py`

**Follow-ups:**
- Why only one repair retry?
- How do you log failures without leaking prompts?

### x008. Where are model selection and cost tracking implemented, and how would you route cheap vs strong models?

`advanced` `[impl]`

**Answer.** NEXUS requests carry a tier (fast or strong): planning and email drafting use fast, evidence analysis uses strong, mapped to configured model names. Each call produces a Usage record with tokens, estimated cost from PRICE_TABLE and latency, stored in usage_records and summarised on the Admin page. A router could additionally downgrade to the fast tier when the remaining run budget is low.

**Why it matters.** Cost awareness is expected for production LLM roles.

**Code:** `nexus-ai/backend/app/llm/base.py:estimate_cost`, `nexus-ai/backend/app/agents/runtime.py:StepContext`, `nexus-ai/backend/app/api/admin.py:usage`

**Follow-ups:**
- How do you keep the price table current?
- How would you A/B test two models?

### x009. You must switch NEXUS and DATAWISE from the local adapter to Gemini in production. Describe a safe rollout.

`senior` `[ext]`

**Answer.** First run the EVALOPS benchmarks with the local provider to get a baseline, then with Gemini behind a flag in staging, comparing citation correctness, SQL result match, abstention or clarification rates, latency and cost; the CI gate blocks if deterministic metrics regress beyond tolerance. Then shadow traffic (log Gemini plans or answers without serving them), then a small canary, keeping the deterministic validators and approval gates unchanged so model errors cannot become unsafe actions. This rollout process is proposed; it has not been executed.

**Why it matters.** Senior question combining evaluation, rollout and safety.

**Code:** `evalops-ai/backend/app/services/gate.py:check_thresholds`, `evalops-ai/backend/app/engine/targets.py:NexusTargetExecutor`, `evalops-ai/backend/app/engine/targets.py:DatawiseTargetExecutor`

**Follow-ups:**
- What metric would block the rollout?
- How do you handle provider outages?

<a id="safety-patterns"></a>
## Safety patterns: grounding, validation, approvals

### x010. Compare how NEXUS and DATAWISE stop the model from causing harm.

`intermediate` `[impl]`

**Answer.** NEXUS lets the model read untrusted text but restricts what it can do: tools are typed and permissioned, and the only side-effecting action (send_email) needs an approval record and a manager. DATAWISE restricts what the model can say: it outputs a QueryPlan over a semantic layer, our compiler writes the SQL, a validator re-checks it, and the database role cannot write. One uses action gating, the other output-space restriction plus least privilege.

**Why it matters.** Distinguishing these two strategies is a strong signal.

**Code:** `nexus-ai/backend/app/tools/registry.py:execute`, `nexus-ai/backend/app/services/approvals.py:approve`, `datawise-ai/backend/app/services/compiler.py:compile_plan`, `datawise-ai/backend/app/services/executor.py:execute_readonly`

**Follow-ups:**
- Could DATAWISE use approvals?
- Could NEXUS restrict its output space further?

### x011. Prompt injection: where is it handled in each project?

`advanced` `[impl]`

**Answer.** NEXUS scans ingested chunks with regex heuristics, flags them, wraps all retrieved text in untrusted_document envelopes, validates citations and analysis sources, and finally requires human approval for sends. DATAWISE runs guardrails on the user's question (destructive intents, system catalogs, injection phrasing) before planning, and even a successful injection can only change a plan that is compiled and validated against allowlists. EVALOPS redacts secrets and PII before storing traces, limiting blast radius if prompts contain sensitive data.

**Why it matters.** Checks layered defense rather than a single filter.

**Code:** `nexus-ai/backend/app/ingestion/injection.py:scan`, `datawise-ai/backend/app/services/guardrails.py:check_question`, `evalops-ai/backend/app/core/redaction.py`

**Follow-ups:**
- Which layer would you remove first under latency pressure?
- How do you test injection defenses?

### x012. Why does DATAWISE validate SQL that its own compiler generated?

`advanced` `[impl]`

**Answer.** Defense in depth: compiler bugs, future features (for example free-text filters) or a manipulated plan could still produce unsafe SQL. validate_sql parses with sqlglot, requires a single SELECT, rejects DML/DDL nodes, and enforces table, column and function allowlists and a row limit. The read-only database role is a third layer that holds even if both application checks fail.

**Why it matters.** Classic defense-in-depth probe.

**Code:** `datawise-ai/backend/app/services/validator.py:validate_sql`, `datawise-ai/docs/adr/0003-defense-in-depth-validator-and-readonly-role.md`

**Follow-ups:**
- What can sqlglot miss?
- How do you test the validator?

### x013. How do idempotency guarantees differ between NEXUS approvals and EVALOPS runs?

`intermediate` `[impl]`

**Answer.** NEXUS uses unique idempotency keys on approval requests and outbox messages plus a row lock while approving, so double clicks or retries send an email exactly once. EVALOPS runs are re-executable by design: reproducibility comes from stored config snapshots and dataset hashes, so repeating a run yields a new, comparable run rather than a deduplicated one. Side effects need idempotency; measurements need reproducibility.

**Why it matters.** Tests whether the candidate understands why the two needs differ.

**Code:** `nexus-ai/backend/app/services/approvals.py:approve`, `nexus-ai/backend/app/models/workflows.py:OutboxMessage`, `evalops-ai/backend/app/engine/runner.py:execute_run`

**Follow-ups:**
- What if the outbox commit succeeds but the HTTP response is lost?
- Should eval runs ever be deduplicated?

### x014. Design a policy layer that all three products could share for tool and data access.

`senior` `[ext]`

**Answer.** Introduce a policy decision point (for example OPA or Cedar) that receives subject (user, role, org), action (tool name or metric), resource and context (side-effect class, data classification) and returns allow, deny or require-approval. NEXUS's tool registry, DATAWISE's compiler (per-metric and per-column permissions) and EVALOPS's dataset access would all call it. Decisions are logged with request ids, and policies are versioned and tested like code. This is a proposed design; today each project enforces roles in its own code.

**Why it matters.** Senior architecture: centralizing authorization without coupling business logic.

**Code:** `nexus-ai/backend/app/tools/registry.py:ToolSpec`, `datawise-ai/backend/app/semantic/layer.py:Metric`

**Follow-ups:**
- What is the latency cost of an external PDP?
- How do you migrate incrementally?

<a id="data-architecture"></a>
## Data architecture and multi-tenancy

### x015. Why does NEXUS keep vectors and relational data in one Postgres while DATAWISE uses two databases?

`intermediate` `[impl]`

**Answer.** NEXUS needs tenant filtering, transactions and joins between chunks, documents and orgs, so pgvector inside the same database keeps org_id filtering atomic with retrieval. DATAWISE separates the app database (users, history, reports) from the analytics database because the analytics side must be reachable only through a read-only role and must never see credentials or app tables.

**Why it matters.** Shows the same tool used differently for different isolation needs.

**Code:** `nexus-ai/docs/adr/ADR-003-hybrid-retrieval-in-postgres.md`, `datawise-ai/docs/adr/0005-two-databases-one-server.md`

**Follow-ups:**
- When would you move vectors to a dedicated store?
- Separate servers or separate databases?

### x016. Multi-tenancy is enforced differently in the three projects. Compare.

`advanced` `[impl]`

**Answer.** NEXUS puts org_id on every tenant table including chunks and filters every query, retrieval call and tool by the caller's org, returning 404 for foreign ids. DATAWISE scopes app data (history, reports, audit) by org, but the synthetic analytics data is shared, which is a documented limitation; real deployments need row-level security or per-tenant schemas. EVALOPS scopes projects, datasets and runs by org and has tenant-isolation API tests.

**Why it matters.** Probes honesty about gaps and knowledge of row-level security.

**Code:** `nexus-ai/backend/app/services/retrieval.py:hybrid_search`, `datawise-ai/docs/roadmap-and-limitations.md`, `evalops-ai/backend/app/api/deps.py`

**Follow-ups:**
- How would Postgres RLS change the code?
- How do you test tenant isolation?

### x017. How are seed data and reproducibility handled, and why does that matter for evaluation?

`intermediate` `[impl]`

**Answer.** Each project seeds with a fixed random seed and a fixed as-of date (NEXUS uses AS_OF 2026-10-31; DATAWISE resolves relative dates against its data end date). That keeps expected answers stable, so EVALOPS benchmarks and DATAWISE's expected-value script produce the same numbers on every machine. Without it, an expected revenue figure would drift with the calendar.

**Why it matters.** Evaluation depends on deterministic fixtures.

**Code:** `nexus-ai/backend/scripts/seed.py`, `datawise-ai/evaluation/build_expected.py`

**Follow-ups:**
- How do you evaluate against live, changing data?
- What breaks if the seed changes?

<a id="evaluation-loop"></a>
## Closing the loop: evaluating NEXUS and DATAWISE with EVALOPS

### x018. How does EVALOPS evaluate NEXUS without importing its code?

`intermediate` `[impl]`

**Answer.** It treats NEXUS as a black-box HTTP target: NexusTargetExecutor logs in, calls POST /api/v1/chat/ask for each test case and maps the response (answer, citations, contexts, usage, latency) into a TargetOutput. Deterministic evaluators then score citation correctness, lexical context precision and recall, groundedness and latency. Because only the documented contract is used, any implementation behind the API can be evaluated.

**Why it matters.** Tests understanding of contract-based evaluation.

**Code:** `evalops-ai/backend/app/engine/targets.py:NexusTargetExecutor`, `evalops-ai/backend/app/evaluators/deterministic.py:citation_correctness`, `MASTER_ARCHITECTURE.md`

**Follow-ups:**
- What if the contract changes?
- How does the evaluator authenticate?

### x019. How does EVALOPS check DATAWISE answers?

`intermediate` `[impl]`

**Answer.** DatawiseTargetExecutor calls POST /api/v1/questions/ask and records the status, SQL, columns and rows. sql_result_match compares returned rows with expected rows using numeric rounding, and status_match checks that ambiguous questions return needs_clarification and unsafe ones return rejected. Expected rows must come from independent SQL, never from the system under test.

**Why it matters.** Independence of expected values is the key insight.

**Code:** `evalops-ai/backend/app/engine/targets.py:DatawiseTargetExecutor`, `evalops-ai/backend/app/evaluators/deterministic.py:sql_result_match`, `evalops-ai/backend/app/evaluators/deterministic.py:status_match`

**Follow-ups:**
- Why not compare SQL text?
- How do you handle row order?

### x020. DATAWISE scores 92.2% overall but only 50% on held-out paraphrases. How do you present that?

`advanced` `[impl]`

**Answer.** Lead with the held-out number as the generalization estimate, because the other categories were authored alongside the rule-based planner and overstate real-world accuracy. Also report that every held-out failure was safe (a clarification request or a missing breakdown, never a wrong number), which matters more for BI than raw accuracy. Then show the plan to improve it: an LLM planner gated by the same eval suite.

**Why it matters.** Integrity and evaluation literacy: train/test contamination.

**Code:** `datawise-ai/docs/evaluation.md`, `datawise-ai/evaluation/run_eval.py`

**Follow-ups:**
- How large should a held-out set be?
- How do you prevent overfitting the eval?

### x021. Why are LLM-judge scores labeled as estimates and kept out of deterministic pass/fail?

`advanced` `[impl]`

**Answer.** Judge scores vary with the judge model, prompt and sampling, can favour verbose answers, and are not reproducible bit-for-bit. Mixing them into gates makes builds flaky and can hide real regressions. EVALOPS stores is_estimate=true, shows an estimate badge, and with the local provider the judge refuses to run instead of fabricating a score.

**Why it matters.** Separating measurement from opinion is a core evaluation concept.

**Code:** `evalops-ai/backend/app/evaluators/judge.py:llm_judge`, `evalops-ai/backend/app/services/gate.py:check_thresholds`

**Follow-ups:**
- When is a judge metric acceptable in a gate?
- How do you calibrate a judge?

### x022. Design a continuous evaluation pipeline that covers all three projects.

`senior` `[impl]`

**Answer.** On every PR: unit and integration tests, then EVALOPS runs the project's golden dataset against the PR build and compares it with the main-branch baseline; the gate fails on regressions beyond tolerance. Nightly: larger benchmarks with real providers, with judge metrics as trend signals. In production: sample live traffic into redacted traces, mine failures into new test cases after human review, and version datasets so scores stay comparable. The production feedback loop is proposed; the CI gate exists.

**Why it matters.** Tests full lifecycle thinking: offline, CI, online.

**Code:** `evalops-ai/backend/app/cli.py`, `evalops-ai/backend/app/services/comparison.py:compare_summaries`, `evalops-ai/backend/app/services/tracing.py:TraceRecorder`

**Follow-ups:**
- How do you keep CI fast?
- Who owns the golden dataset?

<a id="ops-delivery"></a>
## Operations, delivery and cost

### x023. How do you run all three projects locally?

`beginner` `[impl]`

**Answer.** Each project has a docker-compose.yml: NEXUS uses the full profile for api, worker and web; DATAWISE and EVALOPS start db, api and web. Ports are fixed in MASTER_ARCHITECTURE.md (APIs 8101 to 8103) to avoid clashes, and every project has a .env.example with placeholders only. The portfolio is a Vite app that syncs real artifacts from the three projects before building.

**Why it matters.** Basic operability.

**Code:** `README.md`, `MASTER_ARCHITECTURE.md`, `nexus-ai/docker-compose.yml`, `datawise-ai/docker-compose.yml`

**Follow-ups:**
- Why fixed ports?
- How would you run them on Kubernetes?

### x024. What does each CI workflow verify, and what is deliberately not verified?

`intermediate` `[impl]`

**Answer.** Each workflow is path-filtered to its project and runs lint (ruff), types (mypy), backend tests against a Postgres service container, frontend typecheck, tests and build, plus dependency audits; EVALOPS adds an eval-gate job. Not verified in CI: live LLM providers (no keys), cloud deployment, and the Playwright e2e suites, which need a running stack and were run locally. None of the workflows has run on GitHub yet because there is no remote repository.

**Why it matters.** Knowing the limits of your own CI.

**Code:** `.github/workflows/nexus-ci.yml`, `.github/workflows/datawise-ci.yml`

**Follow-ups:**
- How would you add e2e to CI?
- Why use path filters?

### x025. How is observability approached across the projects?

`intermediate` `[impl]`

**Answer.** All three emit structured JSON logs with request ids and redact secret-like fields. NEXUS records audit events for logins, tool calls (including denied and blocked ones) and approvals, plus usage records with tokens, cost and latency. EVALOPS goes furthest with span-level tracing of model, HTTP and tool calls, redaction before storage and optional OTLP export. OpenTelemetry export for NEXUS is a roadmap item.

**Why it matters.** Checks honest, specific answers about observability.

**Code:** `nexus-ai/backend/app/core/logging.py`, `nexus-ai/backend/app/services/audit.py:audit`, `evalops-ai/backend/app/services/tracing.py:TraceRecorder`

**Follow-ups:**
- What would you alert on?
- How would you trace a request across EVALOPS and NEXUS?

### x026. Estimate the cost drivers of running NEXUS with a real LLM and how to control them.

`advanced` `[impl]`

**Answer.** Per question there is one generation call over about six retrieved chunks. Per investigation there is a plan call, one large analysis call over all declining customers, and one draft per declining customer. Controls already present: per-run token budgets checked before each call, fast vs strong tiers, and usage records for attribution. Further controls would be caching embeddings and answers for repeated questions, trimming contexts by rerank score, and batching drafts.

**Why it matters.** Cost reasoning grounded in the actual call graph.

**Code:** `nexus-ai/backend/app/agents/runtime.py:StepContext`, `nexus-ai/backend/app/agents/investigation.py:analysis_agent`

**Follow-ups:**
- Where would caching be unsafe?
- How do you attribute cost per tenant?

<a id="system-design"></a>
## End-to-end system design and trade-offs

### x027. If NEXUS needed to answer 'revenue by region last quarter', would you add SQL generation to NEXUS or call DATAWISE?

`advanced` `[ext]`

**Answer.** Call DATAWISE as a tool. It already owns the semantic layer, validator, read-only execution and its own evaluation suite; duplicating text-to-SQL inside NEXUS would split the safety logic. NEXUS would register a typed tool (for example query_metrics) that calls DATAWISE's ask endpoint with service credentials and treats the returned rows as evidence with provenance, passing clarification responses back to the user. This integration is proposed and not implemented.

**Why it matters.** Composition over duplication; service boundaries.

**Code:** `nexus-ai/backend/app/tools/registry.py:register`, `datawise-ai/backend/app/api/questions.py`

**Follow-ups:**
- How do you propagate the user's permissions?
- What does it do to latency?

### x028. How would you scale NEXUS retrieval from thousands to tens of millions of chunks?

`senior` `[ext]`

**Answer.** Keep pgvector HNSW but partition by org so indexes stay small and tenant filters are cheap, tune ef_search, and move embedding to asynchronous batch jobs. Add a cache for frequent queries. At larger scale or strict latency SLOs, move vectors to a dedicated engine and keep Postgres as the source of truth with outbox-driven sync. Measure recall at k with EVALOPS before and after every change. None of this scaling work has been done yet.

**Why it matters.** Scaling retrieval with evaluation in the loop.

**Code:** `nexus-ai/backend/app/models/documents.py:Chunk`, `nexus-ai/docs/adr/ADR-003-hybrid-retrieval-in-postgres.md`

**Follow-ups:**
- How do tenant filters interact with HNSW?
- What breaks first?

### x029. What would a shared authentication story across the three products look like?

`advanced` `[ext]`

**Answer.** Today each project has its own JWT issuer and seeded users, which is fine for independent demos. In a company you would use an OIDC identity provider issuing tokens with org and role claims, each API validating them via JWKS, and service-to-service calls (EVALOPS to NEXUS) using client-credentials tokens with narrow scopes instead of demo user passwords from environment variables. This is proposed, not implemented.

**Why it matters.** Identity architecture beyond toy JWTs.

**Code:** `nexus-ai/backend/app/core/security.py:decode_access_token`, `evalops-ai/backend/app/engine/targets.py:NexusTargetExecutor`

**Follow-ups:**
- How do you revoke access quickly?
- Where do org claims come from?

### x030. Pick one architecture decision across the projects that you would reverse at 100x scale.

`senior` `[impl]`

**Answer.** The Postgres SKIP LOCKED ingestion queue in NEXUS. It is ideal at small scale (transactional enqueue, no extra service), but at 100x the polling load, lock contention and lack of priorities or delayed retries would hurt. I would move to a managed queue (SQS or Redis streams) with an outbox table to keep enqueueing transactional. The ADR already names this trigger.

**Why it matters.** Shows the candidate knows when their own choices stop working.

**Code:** `nexus-ai/backend/app/ingestion/jobs.py:claim_next`, `nexus-ai/docs/adr/ADR-002-postgres-job-queue.md`

**Follow-ups:**
- What metrics tell you it is time?
- How do you migrate without downtime?

### x031. How do the frontends handle loading, empty and error states?

`intermediate` `[impl]`

**Answer.** Each app has explicit loading indicators, empty states with next-step hints, and error banners showing the API message. NEXUS centralizes this in components/ui.tsx, where ErrorBanner surfaces the request_id from the JSON error envelope, and polling pages (documents, workflow runs) refresh only while work is in progress. DATAWISE renders answered, needs_clarification and rejected states distinctly in its answer panel.

**Why it matters.** UI quality questions are common for full-stack AI roles.

**Code:** `nexus-ai/frontend/src/components/ui.tsx`, `datawise-ai/frontend/src/components/AnswerPanel.tsx`

**Follow-ups:**
- Why show request ids to users?
- How do you avoid polling storms?

### x032. Walk through a request that touches all three systems end to end.

`senior` `[impl]`

**Answer.** A CI job in EVALOPS starts a run: the run engine loads a dataset version and, for a NEXUS case, the target executor logs in and posts to /chat/ask. NEXUS authenticates the JWT, runs hybrid retrieval (pgvector plus full-text, RRF, rerank), calls the provider with untrusted-envelope contexts, validates citations and returns the answer, citations and usage. EVALOPS records a span with redacted attributes, scores the case with deterministic evaluators, aggregates and compares with the baseline, and the gate exits non-zero if a threshold regresses, failing the build.

**Why it matters.** End-to-end fluency across services.

**Code:** `evalops-ai/backend/app/engine/runner.py:execute_run`, `nexus-ai/backend/app/services/chat.py:ask`, `evalops-ai/backend/app/services/gate.py:regression_failures`

**Follow-ups:**
- Where can this be flaky?
- How would you speed it up?

## Coding exercises

### Contract test between EVALOPS and NEXUS (`intermediate`)

Write tests that fail if the NEXUS /api/v1/chat/ask response stops providing the fields that EVALOPS's NexusTargetExecutor reads.

**Solution outline.** Define the contract once (Pydantic model or JSON schema documented in MASTER_ARCHITECTURE.md). In NEXUS, add an API test validating a real response against it. In EVALOPS, add a unit test feeding a recorded response into the executor's mapping.

**Evaluation criteria:**
- Contract defined in one place
- Both sides tested
- Optional fields handled
- No live dependency in unit tests

### A NEXUS tool that calls DATAWISE (`advanced`)

Design and implement a query_metrics tool in NEXUS that asks DATAWISE a question and returns the rows as evidence.

**Solution outline.** Pydantic input/output models; a ToolSpec with side_effect=read and min_role=analyst; an httpx client with timeout and service token; map needs_clarification to a structured result; keep rows plus SQL as provenance; test with httpx.MockTransport.

**Evaluation criteria:**
- Typed IO
- Timeouts and error mapping
- Provenance kept
- Permissions considered
- Tested at the boundary

### Shared redaction library (`intermediate`)

Extract the EVALOPS redaction module into a package that NEXUS logging can use without coupling the projects.

**Solution outline.** Publish a small versioned package of pure functions with a shared test corpus; each project pins a version; project-specific patterns stay in config.

**Evaluation criteria:**
- Pure functions
- Versioning strategy
- Tests with PII samples
- No runtime coupling

### Gate NEXUS on abstention correctness (`advanced`)

Add an abstention-correctness metric (out-of-corpus questions must be answered with insufficient evidence) and gate NEXUS on it.

**Solution outline.** Add test cases with an expected-abstain flag; write a deterministic evaluator that checks the insufficient_evidence flag or phrase; add a threshold to the gate configuration; run baseline and candidate and compare.

**Evaluation criteria:**
- Deterministic definition
- Versioned dataset
- Justified threshold
- Baseline comparison

## Architecture walkthroughs

### Evaluating a NEXUS change in CI

1. A PR modifies NEXUS retrieval code.
2. NEXUS CI runs ruff, mypy and pytest against real Postgres with pgvector.
3. An EVALOPS run executes the NEXUS RAG dataset against the PR build through NexusTargetExecutor.
4. Deterministic evaluators score citations, groundedness and latency; judge metrics run only when a provider key exists.
5. compare_summaries diffs the run against the baseline; the gate exits 1 on regression and the PR is blocked.

### Safety layers side by side

1. Input: NEXUS scans documents at ingestion; DATAWISE checks the question with guardrails.
2. Model output: NEXUS validates citations and sources; DATAWISE checks the plan and compiles the SQL itself.
3. Execution: NEXUS tools check roles; DATAWISE validates the SQL and runs it under a read-only role with a timeout.
4. Side effects: NEXUS requires human approval and idempotent sends; DATAWISE has no side effects by design.
5. Observation: audit events (NEXUS), query history (DATAWISE), redacted traces (EVALOPS).

## Mock interview sequences

### Cross-project screen (`intermediate`)

1. Give a 60-second overview of the three projects and how they relate. (x001)
2. What single design principle is shared by all three projects? (x002)
3. Compare the provider abstractions in NEXUS and DATAWISE. (x006)
4. Compare how NEXUS and DATAWISE stop the model from causing harm. (x010)
5. How are seed data and reproducibility handled, and why does that matter for evaluation? (x017)
6. How do you run all three projects locally? (x023)

### Senior architecture loop (`senior`)

1. You must switch NEXUS and DATAWISE from the local adapter to Gemini in production. Describe a safe rollout. (x009)
2. Design a policy layer that all three products could share for tool and data access. (x014)
3. Why are LLM-judge scores labeled as estimates and kept out of deterministic pass/fail? (x021)
4. How would you scale NEXUS retrieval from thousands to tens of millions of chunks? (x028)
5. Pick one architecture decision across the projects that you would reverse at 100x scale. (x030)
6. Walk through a request that touches all three systems end to end. (x032)
