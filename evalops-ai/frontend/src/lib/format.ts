export function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "--";
  return `${(v * 100).toFixed(digits)}%`;
}

export function num(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "--";
  if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString();
  return v.toFixed(digits);
}

export function ms(v: number | null | undefined): string {
  if (v === null || v === undefined) return "--";
  if (v < 1) return `${v.toFixed(3)} ms`;
  if (v < 1000) return `${v.toFixed(1)} ms`;
  return `${(v / 1000).toFixed(2)} s`;
}

export function usd(v: number | null | undefined): string {
  if (v === null || v === undefined) return "--";
  if (v === 0) return "$0";
  if (Math.abs(v) < 0.01) return `$${v.toFixed(6)}`;
  return `$${v.toFixed(4)}`;
}

/** Signed percentage-point delta, e.g. -18.2 pp. */
export function signedPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "--";
  const s = (v * 100).toFixed(1);
  return v > 0 ? `+${s} pp` : `${s} pp`;
}

export function shortHash(h: string | null | undefined, n = 10): string {
  return h ? h.slice(0, n) : "--";
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "--";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}
