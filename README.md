# AI Engineer Portfolio Workspace

Three independently deployable AI products, a portfolio site, and project-linked interview
preparation. Each project folder is self-contained (own backend, frontend, database, Docker
Compose, CI workflow and docs) and could be split into its own repository unchanged.

| Project | What it is | Local URLs |
|---|---|---|
| [NEXUS AI](nexus-ai/README.md) | Enterprise RAG + LangGraph agents + human-approved actions | web http://localhost:5171 (dev) or :8081 (Docker), API :8101 |
| [DATAWISE AI](datawise-ai/README.md) | Natural-language BI with safe, validated, read-only text-to-SQL | web http://localhost:5172, API :8102 |
| [EVALOPS AI](evalops-ai/README.md) | LLM evaluation, regression detection, tracing, CI gates | web http://localhost:5173, API :8103 |
| [Portfolio](portfolio/README.md) | Recruiter-facing site + interview prep UI | http://localhost:5170 |

Shared conventions and cross-project HTTP contracts: [MASTER_ARCHITECTURE.md](MASTER_ARCHITECTURE.md).
Progress and verification log: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## Prerequisites
- Docker Desktop (running)
- `uv` (Python 3.12 is installed automatically by uv)
- Node 24 (`nvm use 24`); Node >= 20.19 also works for the Vite apps

No LLM API keys are required. Every project defaults to a **deterministic local adapter**,
which is labeled as such in the API responses and the UI. Setting `LLM_PROVIDER=gemini|openai`
plus a key enables real models.

## Start everything (Docker)
```bash
# each project: copy env once (placeholders only), then start
cd nexus-ai    && cp -n .env.example .env && docker compose --profile full up -d --build && cd ..
cd datawise-ai && cp -n .env.example .env && docker compose up -d --build && cd ..
cd evalops-ai  && cp -n .env.example .env && docker compose up -d --build && cd ..
cd portfolio   && npm ci && npm run dev
```
Demo logins use the `DEMO_USER_PASSWORD` value in each project's `.env`:
- NEXUS: `manager@acme.example` (also analyst@, viewer@, admin@acme.example; admin@globex.example)
- DATAWISE: `demo@acme.example` (also analyst@acme.example; demo@globex.example)
- EVALOPS: see `evalops-ai/README.md`

## Interview preparation
- NEXUS: [nexus-ai/interview-preparation/HANDBOOK.md](nexus-ai/interview-preparation/HANDBOOK.md)
- DATAWISE: [datawise-ai/interview-preparation/HANDBOOK.md](datawise-ai/interview-preparation/HANDBOOK.md)
- EVALOPS: [evalops-ai/interview-preparation/HANDBOOK.md](evalops-ai/interview-preparation/HANDBOOK.md)
- Cross-project: [interview-preparation/CROSS_PROJECT.md](interview-preparation/CROSS_PROJECT.md)
- Interactive: portfolio `/interview`

Handbooks are validated by `interview-preparation/render_handbook.py`, which fails if a question
references a file that does not exist.

## Honesty rules used throughout
- No metric is shown unless a committed artifact produced by running code contains it.
- Placeholders (names, links, deployed URLs) are labeled and never presented as live.
- Nothing has been deployed to a cloud; deployment guides are designs plus locally verified Docker images.
