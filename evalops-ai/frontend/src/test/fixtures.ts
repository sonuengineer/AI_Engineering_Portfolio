// Synthetic fixtures for unit tests only -- shaped like API responses, never rendered in the app.
import type { CompareMetricRow, MetricSummary, Span } from "../api/types";

export function metric(overrides: Partial<MetricSummary> = {}): MetricSummary {
  return {
    scored: 4,
    skipped: 0,
    errors: 0,
    passed: 3,
    is_estimate: false,
    gating: true,
    pass_rate: 0.75,
    mean: 0.75,
    ...overrides,
  };
}

export function span(id: string, parent: string | null, startedAt: string, durationMs: number, type = "tool"): Span {
  return {
    id,
    parent_span_id: parent,
    name: id,
    span_type: type,
    started_at: startedAt,
    ended_at: null,
    duration_ms: durationMs,
    status: "ok",
    attributes: { id },
  };
}

export function compareRow(overrides: Partial<CompareMetricRow>): CompareMetricRow {
  return {
    metric: "m",
    baseline_pass_rate: 0.5,
    candidate_pass_rate: 0.5,
    delta: 0,
    tolerance: 0.02,
    is_estimate: false,
    regression: false,
    ...overrides,
  };
}
