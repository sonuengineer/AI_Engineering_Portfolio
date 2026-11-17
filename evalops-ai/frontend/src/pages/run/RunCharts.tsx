import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CaseResult, RunSummary } from "../../api/types";

const BAR = "#1d4ed8"; // single-series bars: one hue, identity named by the chart title
const GRID = "#e2e8f0";
const AXIS = { fontSize: 11, fill: "#475569" };

function ChartCard({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <figure className="rounded-lg border border-slate-200 bg-white p-3">
      <figcaption className="mb-2">
        <span className="block text-sm font-semibold text-slate-900">{title}</span>
        <span className="block text-xs text-slate-600">{desc}</span>
      </figcaption>
      <div className="h-56 w-full">{children}</div>
    </figure>
  );
}

export function RunCharts({ summary, cases }: { summary: RunSummary; cases: CaseResult[] }) {
  const latency = cases
    .filter((c) => c.latency_ms !== null)
    .map((c) => ({ id: c.external_id, latency: Number((c.latency_ms ?? 0).toFixed(4)) }));
  const metrics = Object.entries(summary.metrics)
    .filter(([, m]) => m.pass_rate !== null)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, m]) => ({ name, passRate: Number(((m.pass_rate ?? 0) * 100).toFixed(1)) }));
  const cost = cases.map((c) => ({ id: c.external_id, cost: c.cost_usd }));
  const hasCost = cases.some((c) => c.cost_usd > 0);

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <ChartCard title="Latency per case (ms)" desc={`${latency.length} cases with a recorded latency`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={latency} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="id" tick={AXIS} interval="preserveStartEnd" tickLine={false} />
            <YAxis tick={AXIS} width={52} tickLine={false} axisLine={false} />
            <Tooltip formatter={(v) => [`${v} ms`, "latency"]} cursor={{ fill: "#f1f5f9" }} />
            <Bar dataKey="latency" fill={BAR} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
      <ChartCard title="Pass rate per metric (%)" desc="Metrics with no scored cases (all skipped) are omitted">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={metrics} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="name" tick={AXIS} interval={0} angle={-25} textAnchor="end" height={60} tickLine={false} />
            <YAxis tick={AXIS} domain={[0, 100]} width={40} tickLine={false} axisLine={false} />
            <Tooltip formatter={(v) => [`${v}%`, "pass rate"]} cursor={{ fill: "#f1f5f9" }} />
            <Bar dataKey="passRate" fill={BAR} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
      {hasCost && (
        <ChartCard title="Cost per case (USD)" desc="Estimated from token counts and model-config prices">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={cost} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="id" tick={AXIS} interval="preserveStartEnd" tickLine={false} />
              <YAxis tick={AXIS} width={70} tickLine={false} axisLine={false} tickFormatter={(v: number) => v.toExponential(1)} />
              <Tooltip formatter={(v) => [`$${Number(v).toFixed(6)}`, "cost"]} cursor={{ fill: "#f1f5f9" }} />
              <Bar dataKey="cost" fill={BAR} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}
    </div>
  );
}
