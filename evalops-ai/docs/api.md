# API reference

Base URL `http://localhost:8103` (the Vite dev server proxies `/api`). Interactive OpenAPI docs at
`/docs`. All `/api/v1` routes except login require `Authorization: Bearer <jwt>`.

Errors always use: `{"error": {"code": "...", "message": "...", "request_id": "..."}}` (422s add
`details`). Every response carries `X-Request-ID` (an incoming valid one is echoed).

Roles: `viewer` = read only; `member` = create resources and runs; `admin` = also users + audit.
All resources are scoped to the caller's org; foreign ids return 404.

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | /healthz | -- | process up |
| GET | /readyz | -- | DB reachable (503 otherwise) |
| POST | /api/v1/auth/login | -- | `{email,password}` -> `{access_token, token_type}`; per-IP rate limit |
| GET | /api/v1/auth/me | viewer | current user |
| GET/POST | /api/v1/users | admin | list / create user in own org |
| GET/POST | /api/v1/projects | viewer/member | `{name, slug, description}` |
| GET | /api/v1/projects/{id} | viewer | |
| GET/POST | /api/v1/projects/{id}/datasets | viewer/member | datasets with `versions[]` |
| GET | /api/v1/datasets/{id} | viewer | |
| POST | /api/v1/datasets/{id}/versions | member | multipart `file` (.jsonl/.ndjson, UTF-8, <= MAX_UPLOAD_BYTES), `notes`; identical content returns the existing version |
| GET | /api/v1/dataset-versions/{id}/cases | viewer | `limit`, `offset`, `tag`; total in `X-Total-Count` |
| GET/POST | /api/v1/projects/{id}/prompts | viewer/member | prompt templates with versions |
| POST | /api/v1/prompts/{template_id}/versions | member | `{system_prompt, user_template}`; variables `{{input}}`, `{{contexts}}`, `{{metadata.key}}` |
| GET | /api/v1/providers | viewer | provider list + whether configured |
| GET/POST | /api/v1/projects/{id}/model-configs | viewer/member | `{name, provider, model, params, price_in_per_1k, price_out_per_1k}` |
| GET/POST | /api/v1/projects/{id}/targets | viewer/member | `{name, kind: llm|http_nexus|http_datawise, model_config_id, prompt_version_id, config}`; secrets rejected |
| GET | /api/v1/evaluator-types | viewer | registry: type, kind, description |
| GET/POST | /api/v1/projects/{id}/evaluators | viewer/member | `{name, type, params, threshold, gating}`; judges are forced non-gating |
| GET/POST | /api/v1/projects/{id}/experiments | viewer/member | |
| POST | /api/v1/runs | member | `{project_id, dataset_version_id, target_ids[], evaluator_ids[], experiment_id?, label, concurrency, timeout_s, max_retries, seed}` -> 202 `{run_ids}` (one run per target) |
| GET | /api/v1/runs | viewer | filters `project_id`, `experiment_id`, `status` |
| GET | /api/v1/runs/{id} | viewer | status, progress, summary, config snapshot, provider flags |
| GET | /api/v1/runs/{id}/results | viewer | per-case rows with scores; `failed_only`, `metric`, `tag` |
| POST | /api/v1/runs/{id}/cancel | member | queued runs only |
| GET | /api/v1/compare | viewer | `baseline`, `candidate`, `tolerance` (abs, default 0.02), `latency_tolerance_pct` |
| GET | /api/v1/runs/{id}/traces | viewer | traces (one per case) |
| GET | /api/v1/traces/{id} | viewer | trace with spans (redacted attributes) |
| GET | /api/v1/runs/{id}/report.json, report.md, results.csv | viewer | downloads |
| GET | /api/v1/audit-events | admin | latest audit events |

## Run summary shape (`runs.summary`)

```json
{
  "case_count": 22, "error_count": 0, "error_rate": 0.0,
  "cases_judged": 22, "cases_passed": 14, "overall_pass_rate": 0.636,
  "latency_ms": {"mean": 0.1, "p50": 0.1, "p95": 0.2, "max": 0.3},
  "tokens": {"input": 0, "output": 0, "total": 0}, "cost_usd": 0.0,
  "wall_seconds": 0.4, "throughput_cases_per_sec": 55.0,
  "metrics": {"citations": {"scored": 22, "skipped": 0, "errors": 0, "passed": 19,
                            "pass_rate": 0.864, "mean": 0.864, "is_estimate": false, "gating": true}}
}
```
(Values above illustrate the shape only; real values come from stored runs.)

## Dataset JSONL format

One JSON object per line:

```json
{"id": "qa-001", "input": "When is payment due?", "expected_output": "Within 30 days.",
 "reference_contexts": ["..."], "expected_citations": ["kb-billing-01"], "tags": ["billing"],
 "metadata": {"expected_keywords": ["30 days"], "expected_status": "answered", "expected_rows": [["North", 1.5]],
              "json_schema": {}, "expected_number": 42, "expected_regex": "...", "must_not_contain": ["..."],
              "scripted_outputs": {"v1": {"answer": "...", "citations": ["..."]}}}}
```
Unknown top-level keys are rejected; `metadata` is free-form and read by evaluators.
