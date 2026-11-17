export interface Layer { name: string; items: string[] }
export interface Project {
  slug: "nexus-ai" | "datawise-ai" | "evalops-ai";
  name: string;
  tagline: string;
  summary: string;
  problem: string;
  demoFlow: string[];
  capabilities: { title: string; detail: string }[];
  tech: string[];
  layers: Layer[];
  designDecisions: { title: string; why: string }[];
  docs: { label: string; path: string }[];
  verification: string[];
  limitations: string[];
  accent: string;
}

const commonDocs = (extra: { label: string; path: string }[] = []) => [
  { label: "README", path: "README.md" },
  { label: "Architecture (Mermaid: system, ER, sequences)", path: "docs/architecture.md" },
  { label: "API reference", path: "docs/api.md" },
  { label: "Security and threat model", path: "docs/security-threat-model.md" },
  { label: "Testing strategy and results", path: "docs/testing.md" },
  { label: "Deployment guide", path: "docs/deployment.md" },
  { label: "Architecture decision records", path: "docs/adr/" },
  { label: "Roadmap and limitations", path: "docs/roadmap-and-limitations.md" },
  ...extra,
];

export const PROJECTS: Project[] = [
  {
    slug: "nexus-ai",
    name: "NEXUS AI",
    tagline: "Autonomous enterprise intelligence with grounded answers and human-approved actions",
    summary:
      "Multi-tenant RAG over company documents plus a LangGraph multi-agent system that investigates CRM/ERP/email data, separates evidence from hypotheses, and drafts follow-ups that only send after human approval.",
    problem:
      "Managers ask cross-system questions (why are our best customers buying less?) whose answers are scattered across ERP orders, CRM emails, quotations and documents. A useful assistant must cite sources, avoid inventing causes, and never take external actions on its own.",
    demoFlow: [
      "Supervisor agent validates the goal and plans which agents to run.",
      "Data agent ranks the top 10 customers from ERP and flags those down >= 10%.",
      "Research agent gathers emails, pending quotations and customer-specific document excerpts.",
      "Analysis agent splits EVIDENCE (quoted, sourced) from HYPOTHESES (confidence-rated); ungathered sources are dropped.",
      "Report agent writes the report; action agent drafts emails as approval requests.",
      "A manager edits and approves; the email is delivered exactly once via an idempotent outbox.",
    ],
    capabilities: [
      { title: "Hybrid retrieval", detail: "pgvector HNSW + Postgres full-text, Reciprocal Rank Fusion, reranking, page-level citations." },
      { title: "Checkpointed agents", detail: "Every LangGraph node persists output, enforces timeouts, retries transient errors, respects token budgets and can resume." },
      { title: "Typed tool registry + MCP", detail: "Pydantic-validated tools with role checks and audit; read tools exposed over MCP, send_email never." },
      { title: "Injection defense in depth", detail: "Ingestion scanner, untrusted envelopes, citation and source grounding, plus a human approval gate." },
      { title: "Secure ingestion", detail: "PDF/DOCX/XLSX/CSV/MD with magic-byte checks, zip-bomb and macro rejection, SSRF-safe URL fetch, SKIP LOCKED job queue." },
      { title: "Multi-tenancy and audit", detail: "Org-scoped queries everywhere, RBAC, request ids, audit events, token/cost usage records." },
    ],
    tech: ["Python 3.12", "FastAPI", "SQLAlchemy 2", "PostgreSQL + pgvector", "LangGraph", "MCP", "React 19", "TypeScript", "Tailwind", "Playwright", "Docker"],
    layers: [
      { name: "Experience", items: ["Ask + sources", "Agent activity", "Approvals", "Documents", "Admin"] },
      { name: "API", items: ["JWT + RBAC", "Rate limits", "Request ids", "JSON errors"] },
      { name: "Intelligence", items: ["Hybrid retrieval", "LangGraph supervisor", "5 agents", "LLM providers"] },
      { name: "Tools", items: ["CRM / ERP / email connectors", "search_documents", "approval-gated send_email", "MCP server"] },
      { name: "Data", items: ["Postgres + pgvector", "SKIP LOCKED queue", "Object storage", "Audit + usage"] },
    ],
    designDecisions: [
      { title: "Postgres queue instead of Celery", why: "Transactional enqueue with the document row and one fewer service; scales with N workers." },
      { title: "Retrieval inside Postgres", why: "Tenant filtering and transactions in one place; keyword search rescues exact ids that embeddings miss." },
      { title: "Own step checkpoints around LangGraph", why: "Queryable, UI-friendly step records and resume semantics instead of opaque serialized state." },
      { title: "Approval records for side effects", why: "A prompt-injected agent cannot send email; idempotency keys make retries safe." },
    ],
    docs: commonDocs([{ label: "Performance and evaluation methodology", path: "docs/evaluation-methodology.md" }]),
    verification: [
      "97 backend tests (real Postgres + pgvector), 4 component tests, 4 Playwright e2e tests passing",
      "ruff + mypy clean",
      "Docker stack (api, worker, web, db) built and healthy; e2e passes against it",
    ],
    limitations: [
      "Demo uses a deterministic local adapter; Gemini/OpenAI adapters are not tested live",
      "Local embeddings are lexical (feature hashing), not semantic",
      "S3 storage and OTLP tracing are implemented but only verified against moto / an S3-compatible server and an in-memory exporter, not real AWS or a collector",
      "Not deployed to the cloud",
    ],
    accent: "from-indigo-500 to-blue-600",
  },
  {
    slug: "datawise-ai",
    name: "DATAWISE AI",
    tagline: "Natural-language BI with safe, validated, read-only text-to-SQL",
    summary:
      "Business users ask questions in plain English; a semantic layer turns them into a typed query plan, our compiler produces SQL, a validator enforces allowlists and limits, and a read-only role executes it. Insights are computed only from returned rows.",
    problem:
      "Letting an LLM write SQL against production data risks wrong answers, data leaks and destructive queries. Analysts need answers they can verify: the SQL, the validation result and the rows behind every claim.",
    demoFlow: [
      "User asks e.g. 'monthly revenue by category for the last 6 months'.",
      "Guardrails reject unsafe intents (writes, system catalogs, prompt injection).",
      "Planner produces a typed QueryPlan from the semantic layer, or asks a clarifying question.",
      "Compiler generates SQL; sqlglot validator checks single SELECT, allowlists, functions and LIMIT.",
      "Read-only role executes with statement_timeout and row cap.",
      "Insight text and chart are derived only from the returned rows, with provenance.",
    ],
    capabilities: [
      { title: "Semantic layer", detail: "Metrics, dimensions, synonyms and join paths as the contract between language and SQL." },
      { title: "Plan -> SQL compiler", detail: "Model output is a typed plan, never raw SQL; our code writes the query." },
      { title: "Defense-in-depth validation", detail: "sqlglot AST checks, table/column/function allowlists, LIMIT enforcement, read-only DB role, timeouts." },
      { title: "Clarification", detail: "Ambiguous questions return options instead of guessing." },
      { title: "Grounded insights", detail: "Totals, leaders and period-over-period changes computed in Python from result rows." },
      { title: "Evaluation dataset", detail: "Answerable, ambiguous, unsafe and edge-case questions with independently computed expectations." },
    ],
    tech: ["Python 3.12", "FastAPI", "sqlglot", "PostgreSQL", "SQLAlchemy 2", "React 19", "Recharts", "Docker"],
    layers: [
      { name: "Experience", items: ["Ask + SQL + chart", "History", "Saved reports", "Catalog"] },
      { name: "Pipeline", items: ["Guardrails", "Planner", "Compiler", "Validator", "Executor", "Insights"] },
      { name: "Knowledge", items: ["Semantic layer", "Schema discovery", "Synonyms"] },
      { name: "Data", items: ["App DB", "Analytics DB (read-only role)"] },
    ],
    designDecisions: [
      { title: "Typed plan instead of model-written SQL", why: "Shrinks the attack surface to a schema we control; SQL is generated deterministically." },
      { title: "Validate the compiled SQL anyway", why: "Defense in depth: compiler bugs or future features cannot bypass allowlists." },
      { title: "Read-only role + statement_timeout", why: "The database itself enforces safety even if every app check failed." },
    ],
    docs: commonDocs([{ label: "Evaluation", path: "docs/evaluation.md" }]),
    verification: [
      "149 backend tests against real Postgres (45 validator cases, read-only role refuses writes even in READ WRITE transactions)",
      "8 component tests and 3 Playwright e2e tests (answered / clarification / rejected) passing against the Docker stack",
      "Eval: 71/77 cases (92.2%) with expectations from independent hand-written SQL; held-out paraphrases 6/12, all failures safe (clarification, never a wrong number)",
      "ruff, mypy and pip-audit clean",
    ],
    limitations: [
      "Local rule-based planner generalizes poorly to unseen phrasings (50% on held-out paraphrases); LLM planners exist but are untested live",
      "Analytics data is shared by all orgs; only app data (history, reports, audit) is org-scoped",
      "Relative dates resolve against the synthetic data end date (2026-10-31)",
      "Not deployed to the cloud",
    ],
    accent: "from-emerald-500 to-teal-600",
  },
  {
    slug: "evalops-ai",
    name: "EVALOPS AI",
    tagline: "LLM evaluation, regression detection, tracing and CI quality gates",
    summary:
      "Runs versioned golden datasets against model configs or live AI services, scores them with deterministic evaluators (and clearly labeled judge estimates), compares runs, detects regressions, traces every call with redaction, and fails CI when quality drops.",
    problem:
      "Teams ship prompt and model changes without knowing whether quality regressed. Evaluation must be reproducible, separate measurable facts from LLM-judge opinions, and plug into CI.",
    demoFlow: [
      "Pick a dataset version and targets (model configs or the NEXUS / DATAWISE HTTP APIs).",
      "Run engine executes every case with concurrency limits, timeouts and retries; spans are recorded.",
      "Deterministic evaluators score citations, SQL results, status, latency and cost; judge metrics are labeled estimates.",
      "Compare against a baseline run; regressions and newly failing cases are highlighted.",
      "The CI gate CLI exits non-zero when thresholds or baselines regress.",
    ],
    capabilities: [
      { title: "Deterministic evaluators", detail: "Exact/normalized match, regex, JSON schema, numeric tolerance, citation precision/recall, SQL result match, latency/cost thresholds." },
      { title: "Judge metrics, labeled", detail: "LLM-as-judge with rubrics, always marked as estimates and skipped without a real provider." },
      { title: "Regression detection", detail: "Per-metric tolerance and per-case diffs between runs." },
      { title: "Tracing with redaction", detail: "Spans for prompts, model calls, retrieval, tools and HTTP with PII and secret masking." },
      { title: "CI gate", detail: "CLI and GitHub Actions job that fail the build on regression." },
      { title: "Reproducibility", detail: "Dataset hashes and config snapshots stored per run; exportable reports." },
    ],
    tech: ["Python 3.12", "FastAPI", "PostgreSQL", "SQLAlchemy 2", "OpenTelemetry", "React 19", "Recharts", "GitHub Actions"],
    layers: [
      { name: "Experience", items: ["Runs dashboard", "Compare", "Trace explorer", "Datasets"] },
      { name: "Engine", items: ["Run engine", "Targets", "Evaluators", "Aggregation", "Regression"] },
      { name: "Observability", items: ["Spans", "Redaction", "OTLP export"] },
      { name: "Data", items: ["Datasets + versions", "Runs + results", "Metric scores", "Traces"] },
    ],
    designDecisions: [
      { title: "Deterministic first, judge second", why: "Measurable properties are facts; judge scores are estimates and are labeled as such." },
      { title: "Black-box HTTP targets", why: "Evaluates deployed systems through their public contracts, not their internals." },
      { title: "Gate in CI", why: "Quality regressions block merges the same way failing tests do." },
    ],
    docs: commonDocs([{ label: "Evaluation methodology", path: "docs/evaluation-methodology.md" }, { label: "Live benchmark findings (NEXUS + DATAWISE)", path: "docs/live-benchmark-findings.md" }]),
    verification: [
      "67 backend tests (real Postgres) and 15 frontend tests passing; 2 Playwright e2e tests against the Docker stack",
      "CI eval gate replayed locally: exits 0 for a good candidate and 1 for a regressed one",
      "Benchmarked the live NEXUS and DATAWISE APIs over HTTP (32 and 30 cases); results exported verbatim from stored runs",
      "Found and fixed a benchmark bug (refusal regex) via an immutable dataset v2, keeping v1 for auditability",
    ],
    limitations: [
      "LLM-judge, DeepEval/RAGAS, Gemini/OpenAI and OTLP export paths were never run live (no keys)",
      "Groundedness is a lexical heuristic and currently penalizes correct refusals (documented, fix on roadmap)",
      "Live benchmark numbers describe the local rule-based adapters of NEXUS and DATAWISE, not any LLM",
      "Not deployed to the cloud",
    ],
    accent: "from-amber-500 to-orange-600",
  },
];

export const projectBySlug = (slug: string | undefined) => PROJECTS.find((p) => p.slug === slug);
