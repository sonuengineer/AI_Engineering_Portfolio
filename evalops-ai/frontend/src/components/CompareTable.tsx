import type { CompareMetricRow, CompareOpRow } from "../api/types";
import { ms, pct, signedPct, usd } from "../lib/format";
import { Badge } from "./Badge";

export type DeltaKind = "regression" | "improvement" | "neutral";

/**
 * Classify a metric row. Regressions come from the backend flag. Improvements are
 * deltas above tolerance. Estimate (judge) metrics never gate, so they stay neutral.
 */
export function classifyMetric(row: CompareMetricRow): DeltaKind {
  if (row.is_estimate) return "neutral";
  if (row.regression) return "regression";
  if (row.delta !== null && row.delta > row.tolerance) return "improvement";
  return "neutral";
}

const ROW_CLASS: Record<DeltaKind, string> = {
  regression: "bg-red-50 text-red-900",
  improvement: "bg-green-50 text-green-900",
  neutral: "",
};

export function MetricDeltaTable({ rows }: { rows: CompareMetricRow[] }) {
  return (
    <div className="relative overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full min-w-[600px] text-left text-sm">
        <caption className="sr-only">Per-metric pass-rate deltas, candidate minus baseline</caption>
        <thead className="bg-slate-50 text-xs uppercase text-slate-600">
          <tr>
            <th scope="col" className="px-3 py-2">Metric</th>
            <th scope="col" className="px-3 py-2 text-right">Baseline</th>
            <th scope="col" className="px-3 py-2 text-right">Candidate</th>
            <th scope="col" className="px-3 py-2 text-right">Delta</th>
            <th scope="col" className="px-3 py-2 text-right">Tolerance</th>
            <th scope="col" className="px-3 py-2">Verdict</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => {
            const kind = classifyMetric(r);
            return (
              <tr key={r.metric} data-kind={kind} className={ROW_CLASS[kind]}>
                <th scope="row" className="px-3 py-2 text-left font-mono text-xs font-semibold">
                  {r.metric}{" "}
                  {r.is_estimate && (
                    <Badge tone="purple" title="LLM-judge estimate: reported, never gating">
                      estimate
                    </Badge>
                  )}
                </th>
                <td className="px-3 py-2 text-right tabular-nums">{pct(r.baseline_pass_rate)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{pct(r.candidate_pass_rate)}</td>
                <td className="px-3 py-2 text-right font-semibold tabular-nums">{signedPct(r.delta)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{(r.tolerance * 100).toFixed(1)} pp</td>
                <td className="px-3 py-2">
                  <Verdict kind={kind} estimate={r.is_estimate} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Verdict({ kind, estimate }: { kind: DeltaKind; estimate?: boolean }) {
  if (estimate) return <span className="text-xs text-slate-600">non-gating</span>;
  if (kind === "regression") return <Badge tone="red">regression</Badge>;
  if (kind === "improvement") return <Badge tone="green">improved</Badge>;
  return <span className="text-xs text-slate-600">within tolerance</span>;
}

function fmtOp(name: string, v: number | null): string {
  if (name.includes("latency")) return ms(v);
  if (name.includes("cost")) return usd(v);
  return pct(v);
}

function fmtOpDelta(name: string, v: number | null): string {
  if (v === null) return "--";
  if (name.includes("latency")) return `${v > 0 ? "+" : ""}${ms(v)}`;
  if (name.includes("cost")) return `${v > 0 ? "+" : v < 0 ? "-" : ""}${usd(Math.abs(v))}`;
  return signedPct(v);
}

export function OperationalTable({ rows }: { rows: CompareOpRow[] }) {
  return (
    <div className="relative overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full min-w-[520px] text-left text-sm">
        <caption className="sr-only">Operational metrics, candidate minus baseline</caption>
        <thead className="bg-slate-50 text-xs uppercase text-slate-600">
          <tr>
            <th scope="col" className="px-3 py-2">Measure</th>
            <th scope="col" className="px-3 py-2 text-right">Baseline</th>
            <th scope="col" className="px-3 py-2 text-right">Candidate</th>
            <th scope="col" className="px-3 py-2 text-right">Delta</th>
            <th scope="col" className="px-3 py-2">Verdict</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={r.name} data-kind={r.regression ? "regression" : "neutral"} className={r.regression ? ROW_CLASS.regression : undefined}>
              <th scope="row" className="px-3 py-2 text-left font-mono text-xs font-semibold">
                {r.name}
              </th>
              <td className="px-3 py-2 text-right tabular-nums">{fmtOp(r.name, r.baseline)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtOp(r.name, r.candidate)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtOpDelta(r.name, r.delta)}</td>
              <td className="px-3 py-2">{r.regression ? <Badge tone="red">regression</Badge> : <span className="text-xs text-slate-600">ok</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
