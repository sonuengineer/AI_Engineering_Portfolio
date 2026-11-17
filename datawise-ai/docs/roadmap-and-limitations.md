# Roadmap and limitations

## Known limitations (current state)

| Area | Limitation |
|---|---|
| Language coverage | Local planner: 50% on held-out paraphrases. Unknown synonyms trigger clarification. |
| LLM providers | Gemini/OpenAI code paths are written against verified SDK signatures but never run against live APIs. |
| Query shapes | One fact per question; max 2 dimensions; no window functions, cohorts, period-over-period columns, or "share of total" in SQL (shares are computed in the insight). |
| Comparisons | "2025 vs 2026" becomes a by-year breakdown; arbitrary period comparisons ("this month vs same month last year") are not supported. |
| Time | Relative dates are anchored to `ANALYTICS_AS_OF_DATE` (end of synthetic data), not the wall clock. |
| Multi-tenancy | App data is org-scoped; analytics data is shared (one synthetic company). |
| Auth | JWT in localStorage; no refresh tokens, lockout, SSO or password reset. |
| Rate limiting | In-process token bucket; not shared across replicas. |
| Caching | Value index and catalog cached per process; restart after reseeding to refresh. |
| UI | Not visually inspected in a browser during the autonomous build; behaviour covered by component tests. No dark mode. |
| Guardrails | Regex-based; can false-positive on words like "update" or "remove". |

## Roadmap

1. Run the evaluation with Gemini and OpenAI planners; compare accuracy, cost and latency per
   category (dataset is provider-agnostic).
2. Hybrid planner: local rules first, LLM fallback only when rules would ask for clarification.
3. Semantic layer v2: YAML-defined metrics, derived metrics (margin = revenue - cost), period
   comparison measures, per-metric default time ranges.
4. Row-level security on analytics for real multi-tenant data.
5. httpOnly cookie auth + CSRF, refresh tokens, account lockout.
6. Shared rate limiting (Redis or API gateway) and response caching keyed on compiled SQL.
7. Query cost guard: `EXPLAIN` estimate threshold before execution.
8. Scheduled saved reports with email/Slack delivery.
9. Metric-level join requirements: `Metric` has no joins field, so a metric that needs a joined column
   (e.g. margin using `products.unit_cost`) cannot declare its join yet.
10. Single source for metric display formats (currently duplicated in `frontend/src/components/format.ts`).
