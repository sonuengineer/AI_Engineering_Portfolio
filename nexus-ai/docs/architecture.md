# NEXUS AI -- Architecture

## 1. System overview

```mermaid
flowchart LR
  subgraph Browser
    UI[React SPA<br/>Ask / Investigations / Approvals / Documents / Admin]
  end
  subgraph API["FastAPI (app.main)"]
    MW[Middleware: request id, security headers, CORS, JSON errors]
    AUTH[JWT auth + role checks + rate limit]
    CHAT[services.chat]
    WF[services.workflows]
    APPR[services.approvals]
    DOCS[api.documents]
  end
  subgraph Agents["LangGraph investigation graph"]
    SUP[supervisor] --> DA[data_agent] --> RA[research_agent] --> AA[analysis_agent] --> REP[report_agent] --> ACT[action_agent]
  end
  subgraph Tools["Typed tool registry (tools.registry)"]
    T1[search_customers / get_top_customers / get_customer_orders]
    T2[search_documents / search_emails / get_pending_quotations]
    T3[generate_report / draft_followup_email]
    T4[send_email -- approval required, never MCP-exposed]
  end
  subgraph Ingestion
    Q[(ingestion_jobs<br/>SKIP LOCKED queue)] --> W[worker: extract -> chunk -> scan -> embed]
  end
  LLM[[LLM provider<br/>local | gemini | openai]]
  EMB[[Embedder<br/>local hashing | gemini | openai]]
  PG[(PostgreSQL 17 + pgvector<br/>HNSW + GIN tsvector)]
  OBJ[(Object storage<br/>local dir / S3-compatible)]
  MCP[MCP server<br/>python -m app.mcp_server]

  UI -->|/api/v1| MW --> AUTH
  AUTH --> CHAT & WF & APPR & DOCS
  CHAT --> PG & LLM
  WF --> Agents
  Agents --> Tools
  Agents --> LLM
  APPR --> T4
  Tools --> PG
  DOCS --> OBJ & Q
  W --> OBJ & EMB & PG
  MCP --> Tools
```

Layering (backend/app):

| Layer | Package | Rule |
|---|---|---|
| HTTP | `api/` | Validate input, call a service, serialize. No SQL beyond trivial lookups. |
| Services | `services/` | Business logic, transactions, audit. No FastAPI imports. |
| Agents | `agents/` | LangGraph graph + checkpointed step runtime. Talk to data only through tools. |
| Tools | `tools/` | Typed, permissioned, audited capabilities. Shared by agents and MCP. |
| Connectors | `connectors/` | Data-source adapters (local demo CRM/ERP/email). |
| Ingestion | `ingestion/` | Validation, extraction, chunking, injection scan, SSRF-safe fetch, queue. |
| LLM | `llm/` | Provider abstraction, deterministic local adapter, embeddings, pricing. |

## 2. Data model (ER)

```mermaid
erDiagram
  organizations ||--o{ users : has
  organizations ||--o{ documents : owns
  documents ||--o{ chunks : split_into
  documents ||--o{ ingestion_jobs : processed_by
  users ||--o{ conversations : starts
  conversations ||--o{ messages : contains
  users ||--o{ memory_items : remembers
  organizations ||--o{ crm_customers : has
  crm_customers ||--o{ erp_orders : places
  crm_customers ||--o{ erp_quotations : receives
  crm_customers ||--o{ email_records : exchanges
  users ||--o{ workflow_runs : starts
  workflow_runs ||--o{ workflow_steps : checkpoints
  workflow_runs ||--o{ approval_requests : proposes
  approval_requests ||--o| outbox_messages : executes_once
  organizations ||--o{ audit_events : records
  organizations ||--o{ usage_records : meters

  chunks {
    string id PK
    string org_id FK
    string document_id FK
    int page
    text text
    vector embedding "vector(384), HNSW cosine"
    tsvector tsv "generated, GIN"
    jsonb flags "prompt-injection hits"
  }
  workflow_runs {
    string id PK
    string status "running|awaiting_approval|completed|failed|budget_exceeded|interrupted"
    jsonb state "checkpointed graph state"
    int tokens_used
    int token_budget
  }
  approval_requests {
    string id PK
    string action "send_email"
    jsonb payload
    string status "pending|approved|rejected|executed"
    string idempotency_key UK
  }
```

Every tenant-owned table carries `org_id`; every query filters by the caller's org (tested in
`tests/test_api_integration.py::test_tenant_isolation_documents_and_retrieval`).

## 3. Key workflows

### 3.1 Grounded question answering

```mermaid
sequenceDiagram
  participant U as User
  participant API as /chat/ask
  participant R as hybrid_search
  participant PG as Postgres
  participant L as LLM provider
  U->>API: question (+conversation_id)
  API->>PG: load last 6 messages + user memory items
  API->>R: query, org_id
  R->>PG: pgvector cosine top-25 (org-scoped)
  R->>PG: full-text ts_rank_cd top-25 (org-scoped)
  R->>R: Reciprocal Rank Fusion (k=60) + lexical rerank -> top 6
  API->>L: system rules + contexts wrapped in <untrusted_document>
  L-->>API: GroundedAnswer {answer, cited_context_ids, insufficient_evidence}
  API->>API: validate_citations (drop ids that were not retrieved)
  API->>PG: store messages, usage record, audit event
  API-->>U: answer + citations (doc, page, snippet, flagged) + retrieval debug
```

### 3.2 Ingestion

```mermaid
sequenceDiagram
  participant U as Analyst
  participant API as /documents/upload
  participant S as Object storage
  participant DB as Postgres
  participant W as Worker
  U->>API: multipart file
  API->>API: bounded read, size limit, extension allowlist, magic bytes, zip-bomb + macro checks
  API->>S: put(org/sha256.ext)
  API->>DB: INSERT document + ingestion_job (same transaction)
  API-->>U: 202 pending
  loop poll
    W->>DB: SELECT ... FOR UPDATE SKIP LOCKED (also reclaims stale locks)
  end
  W->>S: get bytes
  W->>W: extract (pypdf/python-docx/openpyxl/csv/md) -> chunk (page/section kept)
  W->>W: injection scan per chunk -> flags
  W->>W: embed in batches
  W->>DB: replace chunks, status=ready (or retry/failed with error)
```

### 3.3 Investigation with human approval

```mermaid
sequenceDiagram
  participant M as Manager
  participant API as /workflows
  participant G as LangGraph
  participant RT as run_step (checkpoint, timeout, retry, budget)
  participant T as Tool registry
  participant A as /approvals
  M->>API: goal
  API-->>M: 202 run_id (graph runs as background task)
  API->>G: invoke(state)
  G->>RT: supervisor -> WorkflowPlan (allowed agents only)
  G->>RT: data_agent -> get_top_customers, get_customer_orders
  G->>RT: research_agent -> search_emails, get_pending_quotations, search_documents (customer excerpts)
  G->>RT: analysis_agent -> EvidenceAnalysis, then ground_sources() drops ungathered sources
  G->>RT: report_agent -> generate_report
  G->>RT: action_agent -> draft_email + draft_followup_email (creates pending approvals only)
  RT->>T: every call: role check, input/output validation, audit
  Note over API: run.status = awaiting_approval
  M->>A: approve (optionally edit subject/body)
  A->>A: SELECT ... FOR UPDATE on approval row
  A->>T: send_email(idempotency_key) -> outbox (exactly once)
  A-->>M: executed; run completes when no approvals are pending
```

## 4. Reliability model for agent workflows

- **Checkpoints**: each node writes `workflow_steps.output` and merges it into
  `workflow_runs.state` in the same transaction. `resume` resets non-completed steps and re-invokes
  the graph; completed steps return their stored output without re-running.
- **Timeouts**: each attempt runs in a worker thread with its own DB session; if it exceeds
  `WORKFLOW_STEP_TIMEOUT_S` the attempt is abandoned and its session is rolled back, so a late
  finisher cannot commit.
- **Retries**: transient exceptions retry with exponential backoff up to
  `WORKFLOW_STEP_MAX_ATTEMPTS`; validation/permission/budget errors fail fast.
- **Budgets**: before every model call the projected token total is checked against the run budget.
- **Crash recovery**: on startup, runs left in `running` are marked `interrupted` and can be resumed.

## 5. Agent graph (generated by LangGraph `draw_mermaid`, simplified)

```mermaid
graph TD
  START([start]) --> supervisor
  supervisor -.-> data_agent
  supervisor -.-> END([end])
  data_agent -.-> research_agent
  research_agent -.-> analysis_agent
  analysis_agent -.-> report_agent
  report_agent -.-> action_agent
  action_agent -.-> END
```
Dotted edges are conditional: routing follows the supervisor's validated plan, so an
`unsupported` goal ends immediately.
