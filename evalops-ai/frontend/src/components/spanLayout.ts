import type { Span } from "../api/types";

export interface SpanRow {
  span: Span;
  depth: number;
  /** ms from trace start to span start */
  offsetMs: number;
  /** span duration in ms (duration_ms, or ended-started, or 0) */
  durationMs: number;
  /** left position in percent of total */
  leftPct: number;
  /** width in percent of total (min width applied by the renderer) */
  widthPct: number;
}

export interface SpanLayout {
  rows: SpanRow[];
  totalMs: number;
}

/**
 * Parse an ISO timestamp to epoch milliseconds keeping sub-millisecond precision
 * (Date.parse truncates microseconds, and our spans are often < 1 ms long).
 */
export function parseIsoMs(iso: string): number {
  const m = /^(.*T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$/.exec(iso);
  if (!m) return Date.parse(iso);
  const base = Date.parse(`${m[1]}${m[3] ?? "Z"}`);
  const frac = m[2] ? Number(`0${m[2]}`) * 1000 : 0;
  return base + frac;
}

/**
 * Lay out spans for a waterfall: tree order (parents before children, siblings by start time),
 * depth from parent chain, offsets relative to the trace start.
 */
export function layoutSpans(spans: Span[], traceStartedAt?: string, traceDurationMs?: number | null): SpanLayout {
  if (spans.length === 0) return { rows: [], totalMs: traceDurationMs ?? 0 };
  const starts = new Map(spans.map((s) => [s.id, parseIsoMs(s.started_at)]));
  const minSpanStart = Math.min(...starts.values());
  const t0 = traceStartedAt ? Math.min(parseIsoMs(traceStartedAt), minSpanStart) : minSpanStart;

  const ids = new Set(spans.map((s) => s.id));
  const children = new Map<string | null, Span[]>();
  for (const s of spans) {
    const parent = s.parent_span_id && ids.has(s.parent_span_id) && s.parent_span_id !== s.id ? s.parent_span_id : null;
    const list = children.get(parent) ?? [];
    list.push(s);
    children.set(parent, list);
  }
  for (const list of children.values()) {
    list.sort((a, b) => (starts.get(a.id) ?? 0) - (starts.get(b.id) ?? 0));
  }

  const ordered: { span: Span; depth: number }[] = [];
  const seen = new Set<string>();
  const visit = (parent: string | null, depth: number) => {
    for (const s of children.get(parent) ?? []) {
      if (seen.has(s.id)) continue;
      seen.add(s.id);
      ordered.push({ span: s, depth });
      visit(s.id, depth + 1);
    }
  };
  visit(null, 0);
  // Spans caught in a parent cycle never reach a root; show them at depth 0.
  for (const s of spans) if (!seen.has(s.id)) ordered.push({ span: s, depth: 0 });

  const measured = ordered.map(({ span, depth }) => {
    const start = starts.get(span.id) ?? t0;
    let dur = span.duration_ms;
    if (dur === null || dur === undefined) dur = span.ended_at ? parseIsoMs(span.ended_at) - start : 0;
    return { span, depth, offsetMs: start - t0, durationMs: Math.max(0, dur) };
  });
  const spanEnd = Math.max(...measured.map((r) => r.offsetMs + r.durationMs));
  const totalMs = Math.max(spanEnd, traceDurationMs ?? 0);
  const rows = measured.map((r) => ({
    ...r,
    leftPct: totalMs > 0 ? (r.offsetMs / totalMs) * 100 : 0,
    widthPct: totalMs > 0 ? (r.durationMs / totalMs) * 100 : 0,
  }));
  return { rows, totalMs };
}

export const SPAN_COLORS: Record<string, string> = {
  prompt: "bg-sky-600",
  model_call: "bg-violet-600",
  retrieval: "bg-amber-600",
  tool: "bg-slate-600",
  http: "bg-teal-600",
  eval: "bg-emerald-600",
};

export function spanColor(type: string): string {
  return SPAN_COLORS[type] ?? "bg-gray-500";
}
