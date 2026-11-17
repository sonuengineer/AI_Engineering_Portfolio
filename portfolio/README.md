# AI Engineer Portfolio Site

Recruiter-facing static site presenting NEXUS AI, DATAWISE AI and EVALOPS AI, plus a
project-linked interview preparation area.

## What is real vs placeholder
- **Real**: project descriptions match the implemented code; screenshots are copied from each
  project's `docs/screenshots` (captured by Playwright e2e runs); metrics come only from
  `<project>/docs/benchmarks/*.json`; interview content comes from
  `<project>/interview-preparation/questions.json` (validated so every code reference exists).
- **Placeholders**: owner name, contact links, repository and live-demo URLs. Set them via
  `VITE_*` variables (see `.env.example`). Unset links render as "not configured" -- never as fake links.

## Run
```bash
nvm use 24
npm ci
npm run dev        # runs the artifact sync, then Vite on http://localhost:5170
npm test           # vitest
npm run build      # sync + typecheck + production build in dist/
```
Docker (build context = workspace root):
```bash
docker build -f portfolio/Dockerfile -t ai-portfolio . && docker run -p 8090:80 ai-portfolio
```

## Pages
- `/` landing page, project cards, skills
- `/projects/:slug` problem, demo flow, architecture preview, capabilities, screenshots,
  measured results, design decisions, verification + limitations, documentation links
- `/interview` hub with per-project progress
- `/interview/:project` practice flow: topic -> difficulty -> question -> reveal answer ->
  follow-ups -> mark learned / bookmark; plus exercises, walkthroughs, mock interviews
  (`/interview/cross-project` for cross-project comparisons)

Progress is stored in the browser's localStorage only (no accounts).
