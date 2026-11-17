# Free hosting guide

Status: **a plan, not a deployment.** Nothing here has been run on any hosting provider; only the
Docker images and the S3 adapter were verified locally. Free-tier terms change often. The numbers
below come from a web search on 2026-11-17 and from vendor pages that were not all readable, so
**check each provider's own pricing page before relying on a limit.**

## What needs hosting

| Piece | Needs | Notes |
|---|---|---|
| portfolio | static files only | cheapest and most useful for recruiters |
| nexus-ai | API, worker, Postgres with **pgvector**, object storage | worker can run inside the API (`INGESTION_MODE=embedded`) |
| datawise-ai | API, web, Postgres with **two databases and a read-only role** | the read-only role is a core safety control, keep it |
| evalops-ai | API, web, Postgres | worker can run inside the API (`RUN_WORKER_IN_API=true`) |

## Recommendation: two tiers

### Tier 0 -- $0, no card, no risk: static portfolio + recorded demos
Host only the portfolio; show the apps through the real screenshots already on the site, and add
short screen recordings. Recruiters rarely need a live API, and a dead demo link looks worse than
none.

- **Cloudflare Pages** (or GitHub Pages). Connect the GitHub repo and use:
  - build command: `cd portfolio && npm ci && npm run build`
  - output directory: `portfolio/dist`
  - environment: `NODE_VERSION=24`
  - Build from the repository root, not from `portfolio/` alone: the build runs
    `scripts/sync-artifacts.mjs`, which reads sibling folders (`../nexus-ai/docs/...`).
  - The site is a single-page app: the host must serve `index.html` for unknown paths (Cloudflare
    Pages does this by default for SPAs; GitHub Pages needs a `404.html` copy and a base path, so I
    recommend Cloudflare Pages).
- Set `VITE_OWNER_NAME`, `VITE_CONTACT_EMAIL`, `VITE_LINKEDIN_URL` in the host's environment
  settings. `portfolio/.env.production` already contains the GitHub URLs.

### Tier 1 -- live demos on one free VM (about $0, more work, more risk)
Run the three compose stacks on a single VM behind Caddy (automatic HTTPS), one subdomain each.

- **Oracle Cloud Always Free (Arm VM).** The free Arm allowance was reported **reduced to 2 OCPU and
  12 GB RAM** in 2026 (older sources and Oracle's cached docs still say 4 OCPU / 24 GB), with
  conflicting enforcement dates reported (June vs 18 August 2026). Reports say instances exceeding
  the allowance are terminated and that idle instances can be **reclaimed without notice** (a
  7-day window was reported but is unverified). Capacity in popular regions is often unavailable,
  and signup needs a card. 12 GB is enough for all three stacks (three Postgres containers, three
  APIs, nginx) but this is untested.
- All images used are multi-arch in principle (`python:3.12-slim`, `node:24-alpine`,
  `nginx`, `postgres:17-alpine`, `pgvector/pgvector:pg17`), but **no stack has been built or run on
  arm64**; expect to debug.
- If Oracle is unavailable, the realistic fallback is the cheapest paid VPS (a few dollars per
  month; check current prices) running the same compose files.

### Tier 2 -- split across free managed services (most fragile)
| Concern | Service | Facts found (verify) | Fit |
|---|---|---|---|
| Postgres + pgvector | **Neon Free** | 1 GB storage per project (20 GB account-wide), 100 compute-hours per project per month, pgvector on all plans, no time limit reported | good for NEXUS and EvalOps; DATAWISE needs a second database and a read-only role created by hand (untested) |
| Object storage | **Cloudflare R2** | 10 GB-month Standard storage, 1M class A and 10M class B operations, no egress fees; S3-compatible | works with NEXUS's `S3Storage` by setting `STORAGE_BACKEND=s3`, `S3_ENDPOINT_URL`, keys and bucket (R2 is untested; SeaweedFS and moto are what was tested) |
| API containers | **Render Free** | spins down after 15 minutes idle and takes about a minute to wake; filesystem is ephemeral; 750 instance-hours per month; **free Postgres expires after 30 days**, so do not use it | usable for demos with a cold start |
| Fly.io | -- | **could not verify** the current free tier | skip unless you check |

Consequences of Render-style spin-down for these apps:
- **Use R2, not local storage** (the filesystem is wiped when the service sleeps).
- NEXUS investigations run as background tasks in the API process: a sleep mid-run leaves the run
  `running`; startup recovery marks it `interrupted` after the staleness window and it can be
  resumed. Ingestion jobs are re-queued by the stale-lock rule.
- The first request after idle takes about a minute; warn visitors on the demo page.

## Hardening checklist (do this before ANY public URL)

- `APP_ENV=production` and a real `JWT_SECRET` (32+ chars). NEXUS refuses to boot otherwise.
- Replace every `DEMO_USER_PASSWORD` placeholder with a strong, unique value, per project. The
  seeded users are public knowledge (the emails are in the docs).
- Never publish Postgres ports. In compose, remove the `ports:` mapping of every `db` service
  on the server (they are published for local development only).
- Terminate TLS at Caddy or the platform; keep `X-Request-ID` and security headers.
- Rate limits are per process (documented): put a WAF or the platform's limits in front.
- Demo data is synthetic. Do not upload real documents to a public demo.
- Do not enable the LLM providers without a spend cap on the provider side; the in-app token
  budget limits runs, not your bill.
- Delete or reset test accounts before publishing (the EvalOps e2e account was already removed).

## Suggested order
1. Tier 0 now (Cloudflare Pages). Fill in the owner placeholders.
2. Record a 60-90 second screen capture per project and link it from each project page.
3. Only then, if you want live demos, try Tier 1 on a free Arm VM and fall back to a cheap VPS.

Sources checked (2026-11-17), all third-party or partially readable, so verify on the vendor pages:
- AWS Free Tier FAQs: https://aws.amazon.com/free/faqs/
- Oracle Always Free resources: https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing
- Neon free plan limits: https://neon.com/faqs/free-plan-limits-and-quotas
- Render free tier: https://render.com/docs/free
