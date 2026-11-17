import { useState } from "react";
import type { Span } from "../api/types";
import { ms } from "../lib/format";
import { Badge } from "./Badge";
import { SPAN_COLORS, layoutSpans, spanColor } from "./spanLayout";

interface Props {
  spans: Span[];
  traceStartedAt?: string;
  traceDurationMs?: number | null;
}

export function SpanWaterfall({ spans, traceStartedAt, traceDurationMs }: Props) {
  const { rows, totalMs } = layoutSpans(spans, traceStartedAt, traceDurationMs);
  const [selectedId, setSelectedId] = useState<string | null>(rows[0]?.span.id ?? null);
  const selected = rows.find((r) => r.span.id === selectedId) ?? null;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <section aria-label="Span waterfall" className="rounded-lg border border-slate-200 bg-white p-3">
        <div className="mb-2 flex flex-wrap gap-2 text-xs" aria-label="Span type legend">
          {Object.entries(SPAN_COLORS).map(([type, cls]) => (
            <span key={type} className="inline-flex items-center gap-1 text-slate-700">
              <span className={`inline-block h-2.5 w-2.5 rounded-sm ${cls}`} aria-hidden="true" />
              {type}
            </span>
          ))}
          <span className="ml-auto text-slate-600">total {ms(totalMs)}</span>
        </div>
        <ul className="space-y-1">
          {rows.map((r) => {
            const isSel = r.span.id === selectedId;
            return (
              <li key={r.span.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(r.span.id)}
                  aria-pressed={isSel}
                  data-testid="span-row"
                  className={`grid w-full grid-cols-[minmax(0,2fr)_minmax(0,3fr)] items-center gap-2 rounded px-1 py-1 text-left text-xs hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-blue-600 ${
                    isSel ? "bg-blue-50 ring-1 ring-blue-300" : ""
                  }`}
                >
                  <span className="truncate font-mono" style={{ paddingLeft: `${r.depth * 12}px` }}>
                    {r.span.status !== "ok" && <span className="mr-1 text-red-700">!</span>}
                    {r.span.name}
                  </span>
                  <span className="relative block h-4 rounded bg-slate-100">
                    <span
                      className={`absolute top-0 h-4 rounded ${spanColor(r.span.span_type)}`}
                      style={{ left: `${Math.min(r.leftPct, 99)}%`, width: `max(${r.widthPct}%, 3px)` }}
                      title={`${r.span.span_type}: ${ms(r.durationMs)} at +${ms(r.offsetMs)}`}
                    />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>
      <section aria-label="Span details" aria-live="polite" className="rounded-lg border border-slate-200 bg-white p-3">
        {selected ? (
          <>
            <h3 className="break-all font-mono text-sm font-semibold">{selected.span.name}</h3>
            <div className="mt-1 flex flex-wrap gap-1.5">
              <Badge tone="blue">{selected.span.span_type}</Badge>
              <Badge tone={selected.span.status === "ok" ? "green" : "red"}>{selected.span.status}</Badge>
            </div>
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 text-xs text-slate-700">
              <dt>offset</dt>
              <dd className="tabular-nums">+{ms(selected.offsetMs)}</dd>
              <dt>duration</dt>
              <dd className="tabular-nums">{ms(selected.durationMs)}</dd>
              <dt>depth</dt>
              <dd>{selected.depth}</dd>
            </dl>
            <h4 className="mt-3 text-xs font-semibold uppercase text-slate-600">Attributes (redacted)</h4>
            <pre className="mt-1 max-h-96 overflow-auto rounded bg-slate-900 p-2 text-xs whitespace-pre-wrap break-words text-slate-100">
              {JSON.stringify(selected.span.attributes, null, 2)}
            </pre>
          </>
        ) : (
          <p className="text-sm text-slate-600">Select a span to see its attributes.</p>
        )}
      </section>
    </div>
  );
}
