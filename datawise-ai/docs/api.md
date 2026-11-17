# API reference

Base URL (dev): `http://localhost:8102` (or through the web proxy at `http://localhost:5172/api/...`).
Interactive OpenAPI docs: `http://localhost:8102/docs`.

All errors use one envelope and echo the request id header:

```json
{"error": {"code": "invalid_credentials", "message": "Invalid email or password", "request_id": "7b57..."}}
```

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /healthz | no | process is up |
| GET | /readyz | no | app DB + analytics DB reachable (503 otherwise) |
| POST | /api/v1/auth/login | no | email + password -> JWT |
| GET | /api/v1/auth/me | yes | current user + org |
| POST | /api/v1/questions/ask | yes | the question pipeline (rate limited) |
| GET | /api/v1/history?limit=50 | yes | query history of the caller's org |
| GET/POST | /api/v1/reports | yes | list / create saved reports |
| GET/PATCH/DELETE | /api/v1/reports/{id} | yes | read / rename / delete (org-scoped, 404 for other orgs) |
| POST | /api/v1/reports/{id}/run | yes | re-run the stored plan (no planner call) |
| GET | /api/v1/catalog | yes | information_schema of allowlisted tables + semantic layer |

## Login

```bash
curl -s -X POST localhost:8102/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"demo@acme.example","password":"<DEMO_USER_PASSWORD>"}'
# {"access_token":"eyJ...","token_type":"bearer"}
```

## Ask -- answered

```bash
curl -s -X POST localhost:8102/api/v1/questions/ask \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"question":"Top 5 products by revenue in 2025"}'
```

Response (real output, rows trimmed):

```json
{
  "status": "answered",
  "plan": {"metrics": ["revenue"], "dimensions": ["product"], "filters": [],
           "time_range": {"start": "2025-01-01", "end": "2026-01-01", "label": "2025"},
           "order_by": [{"field": "revenue", "direction": "desc"}], "limit": 5,
           "assumptions": ["Cancelled orders are excluded from sales metrics."]},
  "sql": "SELECT p.name AS product, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue\nFROM orders o JOIN order_items oi ON oi.order_id = o.order_id\nJOIN products p ON p.product_id = oi.product_id\nWHERE o.status <> 'cancelled' AND o.order_date >= CAST('2025-01-01' AS DATE) AND o.order_date < CAST('2026-01-01' AS DATE)\nGROUP BY 1\nORDER BY revenue DESC, product ASC\nLIMIT 5",
  "validation": {"ok": true, "issues": []},
  "columns": ["product", "revenue"],
  "rows": [["Running Shoes", 289177.49], ["Webcam", 207996.06], ["Smart Speaker", 185794.54]],
  "row_count": 5,
  "insight": "Highest revenue: Running Shoes at $289,177.49 (31.2% of the 5 rows shown). Lowest: Noise-Cancel Headphones at $111,358.53. Total across rows shown: $925,794.49 (2025).",
  "clarification": null,
  "rejection_reason": null,
  "provider": "local",
  "model": "rules-v1",
  "latency_ms": 41,
  "query_id": 1,
  "chart": {"type": "bar", "x": "product", "y": ["revenue"], "series": null},
  "insight_provenance": [{"columns": ["product", "revenue"], "row_indexes": [0], "note": "max row"}],
  "usage": {"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
}
```

Fields from `query_id` down are additive to the contract in MASTER_ARCHITECTURE.md section 3.

## Ask -- needs clarification

```json
{"status": "needs_clarification", "sql": null, "rows": [],
 "clarification": {"question": "How should customers be ranked? Choose a measure.",
                   "options": ["Top 10 customers by revenue", "Top 10 customers by order count",
                               "Top 10 customers by units sold"]},
 "provider": "local", "...": "..."}
```

Options are complete questions: the client simply re-sends one as a new `question`.

## Ask -- rejected

```json
{"status": "rejected", "sql": null,
 "validation": {"ok": false, "issues": ["guardrail:write_intent"]},
 "rejection_reason": "DATAWISE is read-only: it cannot create, change or delete data, users or permissions.",
 "provider": "local", "...": "..."}
```

A plan whose compiled SQL fails validation is also `rejected`, with `sql` set and the validator
issues in `validation.issues` (the SQL is not executed).

## Execution failures

Database-side failures are not a fourth status; they return the error envelope:
`504 query_timeout` (statement timeout), `502 execution_error`, `502 analytics_unavailable`,
`502 planner_error` (LLM provider failed after one repair retry), `429 rate_limited`.

## Saved reports

```bash
# save the plan returned by /ask
curl -s -X POST localhost:8102/api/v1/reports -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"name":"Top products 2025","question":"Top 5 products by revenue in 2025","plan":{...plan from ask...}}'
# re-run (same compiler + validator + executor; no planner)
curl -s -X POST localhost:8102/api/v1/reports/1/run -H "authorization: Bearer $TOKEN"
```
