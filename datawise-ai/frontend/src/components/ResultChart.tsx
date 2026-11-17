import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Cell, ChartSpec } from "../types";
import { formatCell, formatPeriod, isTimeColumn } from "./format";

const COLORS = ["#0f766e", "#4f46e5", "#d97706", "#db2777", "#0284c7", "#65a30d", "#7c3aed", "#dc2626"];

type Point = Record<string, string | number | null>;

/** Turns rows into recharts points; with a series column the rows are pivoted into one key per series value. */
export function toChartData(spec: ChartSpec, columns: string[], rows: Cell[][]): { data: Point[]; keys: string[] } {
  const xi = columns.indexOf(spec.x ?? "");
  const yName = spec.y[0] ?? "";
  if (xi < 0) return { data: [], keys: [] };
  const fmtX = (v: Cell) => (isTimeColumn(spec.x ?? "") ? formatPeriod(spec.x ?? "", v) : String(v ?? ""));
  if (!spec.series) {
    const data = rows.map((r) => {
      const p: Point = { [spec.x ?? "x"]: fmtX(r[xi] ?? null) };
      spec.y.forEach((y) => {
        const v = r[columns.indexOf(y)];
        p[y] = typeof v === "number" ? v : null;
      });
      return p;
    });
    return { data, keys: spec.y };
  }
  const si = columns.indexOf(spec.series);
  const yi = columns.indexOf(yName);
  const byX = new Map<string, Point>();
  const keys: string[] = [];
  rows.forEach((r) => {
    const x = fmtX(r[xi] ?? null);
    const s = String(r[si] ?? "");
    if (!keys.includes(s)) keys.push(s);
    const p = byX.get(x) ?? { [spec.x ?? "x"]: x };
    const v = r[yi];
    p[s] = typeof v === "number" ? v : null;
    byX.set(x, p);
  });
  return { data: [...byX.values()], keys: keys.slice(0, 8) };
}

export function ResultChart({ spec, columns, rows }: { spec: ChartSpec; columns: string[]; rows: Cell[][] }) {
  if (spec.type === "table" || !spec.x) return null;
  const { data, keys } = toChartData(spec, columns, rows);
  if (!data.length) return null;
  const metric = spec.y[0] ?? "";
  const tick = (v: number) => formatCell(metric, v);
  const tooltip = (v: unknown) => (typeof v === "number" ? formatCell(metric, v) : String(v));
  return (
    <figure aria-label={`${spec.type} chart of ${spec.y.join(", ")} by ${spec.x}`} className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {spec.type === "line" ? (
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={spec.x} tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={tick} tick={{ fontSize: 11 }} width={80} />
            <Tooltip formatter={tooltip} />
            {keys.length > 1 ? <Legend /> : null}
            {keys.map((k, i) => (
              <Line key={k} type="monotone" dataKey={k} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} isAnimationActive={false} />
            ))}
          </LineChart>
        ) : (
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={spec.x} tick={{ fontSize: 11 }} interval={0} angle={data.length > 6 ? -30 : 0} textAnchor={data.length > 6 ? "end" : "middle"} height={data.length > 6 ? 70 : 30} />
            <YAxis tickFormatter={tick} tick={{ fontSize: 11 }} width={80} />
            <Tooltip formatter={tooltip} />
            {keys.length > 1 ? <Legend /> : null}
            {keys.map((k, i) => (
              <Bar key={k} dataKey={k} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </figure>
  );
}
