import type { ReactNode } from "react";

export type Tone = "gray" | "green" | "red" | "amber" | "blue" | "purple";

const TONES: Record<Tone, string> = {
  gray: "bg-slate-100 text-slate-800 border-slate-300",
  green: "bg-green-50 text-green-800 border-green-300",
  red: "bg-red-50 text-red-800 border-red-300",
  amber: "bg-amber-50 text-amber-900 border-amber-300",
  blue: "bg-blue-50 text-blue-800 border-blue-300",
  purple: "bg-purple-50 text-purple-800 border-purple-300",
};

export function Badge({ tone = "gray", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center whitespace-nowrap rounded border px-1.5 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

const STATUS_TONE: Record<string, Tone> = {
  completed: "green",
  failed: "red",
  running: "blue",
  queued: "amber",
  cancelled: "gray",
};

export function StatusPill({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "gray"}>{status}</Badge>;
}

export function PassPill({ passed }: { passed: boolean | null }) {
  if (passed === null) return <Badge tone="gray">n/a</Badge>;
  return passed ? <Badge tone="green">pass</Badge> : <Badge tone="red">fail</Badge>;
}

export function DeterministicBanner() {
  return (
    <div
      role="note"
      className="rounded-md border-2 border-amber-400 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900"
    >
      Deterministic local adapter / scripted fixture -- not a real LLM
    </div>
  );
}
