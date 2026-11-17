import type { MetricSummary } from "../api/types";
import { num, pct } from "../lib/format";
import { Badge } from "./Badge";

interface MetricCardProps {
  name: string;
  metric: MetricSummary;
  /** Explanation from a skipped case score, shown when every case was skipped. */
  skipReason?: string | null;
}

export function MetricCard({ name, metric, skipReason }: MetricCardProps) {
  const allSkipped = metric.scored === 0 && metric.skipped > 0;
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm" aria-label={`metric ${name}`}>
      <header className="flex flex-wrap items-center gap-1.5">
        <h3 className="mr-auto break-all font-mono text-sm font-semibold text-slate-900">{name}</h3>
        {metric.is_estimate && (
          <Badge tone="purple" title="LLM-judge score: an estimate, never gates pass/fail">
            estimate
          </Badge>
        )}
        {!metric.gating && <Badge tone="gray">non-gating</Badge>}
      </header>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900">{pct(metric.pass_rate)}</p>
      <dl className="mt-1 grid grid-cols-2 gap-x-2 text-xs text-slate-600">
        <dt>mean</dt>
        <dd className="text-right tabular-nums">{num(metric.mean, 3)}</dd>
        <dt>passed / scored</dt>
        <dd className="text-right tabular-nums">
          {metric.passed} / {metric.scored}
        </dd>
        <dt>skipped</dt>
        <dd className="text-right tabular-nums">{metric.skipped}</dd>
        {metric.errors > 0 && (
          <>
            <dt>errors</dt>
            <dd className="text-right tabular-nums text-red-700">{metric.errors}</dd>
          </>
        )}
      </dl>
      {allSkipped && (
        <p className="mt-2 rounded bg-slate-100 p-1.5 text-xs text-slate-700">
          All cases skipped{skipReason ? `: ${skipReason.replace(/^skipped:\s*/i, "")}` : ""}
        </p>
      )}
    </article>
  );
}

export function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-600">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-slate-900">{value}</p>
      {hint && <p className="text-xs text-slate-600">{hint}</p>}
    </div>
  );
}
