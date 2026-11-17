# Architecture

## Components

```mermaid
flowchart LR
  subgraph Browser
    UI[React 19 dashboard<br/>Vite :5173]
  end
  subgraph EvalOps
    API[FastAPI :8103<br/>auth, CRUD, runs, compare,<br/>traces, reports]
    W[Run worker<br/>SKIP LOCKED queue<br/>thread pool per run]
    CLI[CLI<br/>run / gate / ci-gate]
    DB[(PostgreSQL 17<br/>:5443)]
  end
  subgraph Targets
    L[local / mock_scripted<br/>deterministic adapters]
    G[Gemini / OpenAI<br/>optional, keys via env]
    N[NEXUS AI :8101<br/>/api/v1/chat/ask]
    D[DATAWISE AI :8102<br/>/api/v1/questions/ask]
  end
  OTEL[(OTLP collector<br/>optional)]
  UI -- /api proxy --> API
  API --> DB
  W --> DB
  CLI --> DB
  W --> L & G & N & D
  W -. redacted spans .-> OTEL
```

- **API** (`backend/app/api`) is thin: validate -> call a service -> serialize. Every query is
  filtered by the caller's `org_id` (multi-tenancy).
- **Run engine** (`backend/app/engine`): `create_runs` freezes a config snapshot (target, model
  config, prompt version text + hash, evaluator configs, dataset version + content hash, seed,
  concurrency/timeout/retries, git sha) and inserts `runs` rows with status `queued`. A worker claims
  one with `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)` and executes all cases
  in a bounded thread pool. Per case: call the target (retries with exponential backoff + seeded
  jitter on transient errors), record spans, run evaluators, persist result + scores + trace.
  At the end the run summary (aggregates) is computed and stored on the run.
- **Worker placement**: embedded in the API process in dev (`RUN_WORKER_IN_API=true`), a separate
  `worker` container in docker compose. Multiple workers are safe thanks to SKIP LOCKED.
- **Evaluators** (`backend/app/evaluators`): pure functions registered by type. `kind=deterministic`
  or `kind=judge`. Judge scores are always `is_estimate=true` and never gate case pass/fail.
- **Tracing** (`backend/app/services/tracing.py`): in-memory span recorder per case, redacted by
  `core/redaction.py` before it is written to `traces`/`spans`, optionally exported over OTLP.

## Data model (ER)

```mermaid
erDiagram
  orgs ||--o{ users : has
  orgs ||--o{ projects : owns
  projects ||--o{ datasets : has
  datasets ||--o{ dataset_versions : "immutable versions"
  dataset_versions ||--o{ test_cases : contains
  projects ||--o{ prompt_templates : has
  prompt_templates ||--o{ prompt_versions : versions
  projects ||--o{ model_configs : has
  projects ||--o{ targets : has
  targets }o--o| model_configs : "llm kind"
  targets }o--o| prompt_versions : "llm kind"
  projects ||--o{ evaluator_configs : has
  projects ||--o{ experiments : groups
  experiments ||--o{ runs : contains
  runs }o--|| dataset_versions : "evaluates"
  runs }o--|| targets : "against"
  runs ||--o{ run_results : "one per case"
  run_results ||--o{ metric_scores : scored_by
  runs ||--o{ traces : records
  traces ||--o{ spans : contains
  orgs ||--o{ audit_events : logs
```

Every tenant-owned table has `org_id`. `dataset_versions.content_hash` is a SHA-256 over the
canonical JSON of the cases; re-uploading identical content returns the existing version.

## Run sequence

```mermaid
sequenceDiagram
  participant U as UI / CLI
  participant A as API
  participant DB as Postgres
  participant W as Worker
  participant T as Target
  U->>A: POST /api/v1/runs
  A->>DB: insert runs(status=queued, config_snapshot)
  A-->>U: 202 {run_ids}
  loop poll
    U->>A: GET /api/v1/runs/{id}
  end
  W->>DB: claim queued run (FOR UPDATE SKIP LOCKED)
  par per case (bounded concurrency)
    W->>T: call (timeout, retries w/ backoff)
    T-->>W: output
    W->>W: evaluators (deterministic + judge)
    W->>DB: run_result + metric_scores + redacted trace/spans
  end
  W->>DB: summary aggregates, status=completed
  U->>A: GET /runs/{id}, /results, /compare, /traces, /report.*
```

## Deviations from MASTER_ARCHITECTURE.md

- The MASTER doc lists `llm/` provider names `local|gemini|openai`. EvalOps adds a fourth
  deterministic provider, `mock_scripted`, which replays outputs scripted in the dataset to make
  regression demos reproducible. It is labeled as a fixture everywhere.
- NEXUS returns database UUIDs as `document_id`, which change on every NEXUS reseed. The
  `http_nexus` target therefore matches citations on `document_title` by default
  (`target.config.citation_key`).
- Optional DeepEval/RAGAS integrations are installed manually (not uv extras) because they conflict
  with `openai==3.51` in one lock file.
