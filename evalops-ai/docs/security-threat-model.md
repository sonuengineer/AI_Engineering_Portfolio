# Security threat model

Scope: EvalOps API, worker, dashboard, Postgres, and outbound calls to LLM providers and the NEXUS /
DATAWISE APIs. Method: STRIDE-style walk over the main assets.

## Assets

- Datasets (may contain customer questions / PII), model outputs, traces.
- Credentials: JWT signing key, provider API keys, target app credentials, DB password.
- Integrity of evaluation results (a tampered score could ship a regression).

## Threats and controls

| Threat | Control | Residual risk |
|---|---|---|
| Cross-tenant data access | `org_id` on every tenant row; every query filters by caller org; foreign ids -> 404; tested across 10 endpoints | a new endpoint that forgets the filter; mitigated by tests, no row-level security yet |
| Credential theft from DB | target configs store env var *names* only; secret-looking keys rejected (422); passwords argon2-hashed | env vars readable by anyone with host access |
| Secrets/PII in traces and logs | `core/redaction.py` masks emails, phones, bearer tokens, JWTs, common API key formats, `key=value` secrets, Luhn-valid card numbers, and sensitive dict keys before storage/export; logs carry no prompts/outputs | regex redaction misses novel formats, names, addresses (not a DLP system); run outputs are stored unredacted in `run_results` because evaluators need them |
| Token forgery / replay | HS256 JWT with exp, `require` claims; short default lifetime (60 min) | no revocation list; secret must be strong |
| Brute force login | per-IP token bucket on login; uniform error message; failed logins audited | limiter is per process |
| Privilege escalation | role ranks viewer < member < admin enforced by dependencies; judges cannot be made gating | -- |
| Malicious dataset upload | extension + content-type allowlist, size cap (413), case cap, strict schema (unknown keys rejected), UTF-8 only, no file stored on disk | large JSON objects within the size cap |
| Prompt injection via dataset/target output | outputs are only scored, never executed; EvalOps has no tools/agents that act on outputs; NEXUS benchmark includes an injection case to test the *target* | an LLM judge could be swayed by injected text (scores are estimates and non-gating) |
| SSRF via target base_url | base URLs come from env or target config created by members | a member could point a target at an internal URL; restrict egress in production (roadmap: allowlist) |
| Tampering with results | results written only by the worker; runs keep config snapshot + dataset hash; audit events for creates | DB admins can edit rows; no signing of reports |
| DoS via huge runs | concurrency clamped to 32, timeout <= 300 s, retries <= 5, rate limits | no per-org quota |
| XSS in dashboard | React escaping, no `dangerouslySetInnerHTML`; nginx/API set `X-Content-Type-Options`, `X-Frame-Options` | no CSP header yet |

## Data handling

- `.env` is git-ignored and excluded from Docker build context; `.env.example` has placeholders only.
- Demo passwords come from `DEMO_USER_PASSWORD`; nothing is hardcoded in the source.
