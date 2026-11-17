import type { Cell } from "../types";

const PERCENT = new Set(["conversion_rate", "on_time_delivery_rate"]);
const CURRENCY = new Set(["revenue", "avg_order_value"]);
const TIME = new Set(["month", "quarter", "year"]);

export function formatPeriod(dim: string, v: Cell): string {
  const s = String(v ?? "");
  if (!TIME.has(dim) || s.length < 10) return s;
  const y = s.slice(0, 4);
  const m = Number(s.slice(5, 7));
  if (dim === "month") return `${y}-${String(m).padStart(2, "0")}`;
  if (dim === "quarter") return `${y}-Q${Math.floor((m - 1) / 3) + 1}`;
  return y;
}

export function formatCell(column: string, v: Cell): string {
  if (v === null || v === undefined) return "--";
  if (TIME.has(column)) return formatPeriod(column, v);
  if (typeof v !== "number") return String(v);
  if (PERCENT.has(column)) return `${(v * 100).toFixed(1)}%`;
  if (CURRENCY.has(column)) return v.toLocaleString("en-US", { style: "currency", currency: "USD" });
  return v.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function isTimeColumn(c: string): boolean {
  return TIME.has(c);
}
