import type { ButtonHTMLAttributes, ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "danger" | "ghost";
export function Button({ variant = "primary", busy, className, children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  const styles: Record<Variant, string> = {
    primary: "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-600/50",
    secondary: "bg-white text-slate-800 border border-slate-300 hover:bg-slate-50 disabled:opacity-50",
    danger: "bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-600/50",
    ghost: "text-slate-700 hover:bg-slate-100",
  };
  return (
    <button {...rest} disabled={rest.disabled || busy} aria-busy={busy || undefined}
      className={cx("inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed", styles[variant], className)}>
      {busy && <Spinner small />}
      {children}
    </button>
  );
}

export function Card({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-xl border border-slate-200 bg-white shadow-sm", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

const tones = {
  slate: "bg-slate-100 text-slate-700", green: "bg-emerald-100 text-emerald-800", amber: "bg-amber-100 text-amber-800",
  red: "bg-rose-100 text-rose-800", blue: "bg-brand-100 text-brand-900", violet: "bg-violet-100 text-violet-800",
};
export function Badge({ tone = "slate", children, title }: { tone?: keyof typeof tones; children: ReactNode; title?: string }) {
  return <span title={title} className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>{children}</span>;
}

const STATUS_TONE: Record<string, keyof typeof tones> = {
  ready: "green", completed: "green", executed: "green", approved: "green",
  pending: "amber", processing: "blue", running: "blue", awaiting_approval: "violet",
  failed: "red", rejected: "red", budget_exceeded: "red", interrupted: "amber",
};
export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "slate"}>{status.replace(/_/g, " ")}</Badge>;
}

export function Spinner({ small }: { small?: boolean }) {
  return <span role="status" aria-label="Loading" className={cx("inline-block animate-spin rounded-full border-2 border-current border-t-transparent", small ? "h-3.5 w-3.5" : "h-5 w-5")} />;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="flex items-center gap-2 p-6 text-sm text-slate-500"><Spinner />{label}...</div>;
}

export function ErrorBanner({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  const e = error as { message?: string; requestId?: string };
  return (
    <div role="alert" className="flex items-start justify-between gap-3 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
      <div>
        <p className="font-medium">{e.message ?? "Something went wrong"}</p>
        {e.requestId && <p className="mt-0.5 text-xs text-rose-700/80">Request ID: {e.requestId}</p>}
      </div>
      {onRetry && <Button variant="secondary" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {children && <div className="mt-1 text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function ProviderBadge({ provider }: { provider: string }) {
  return provider === "local"
    ? <Badge tone="amber" title="Answers come from a deterministic rule-based adapter, not a live LLM. Set LLM_PROVIDER=gemini or openai with an API key for model-generated output.">Deterministic local adapter</Badge>
    : <Badge tone="blue">LLM: {provider}</Badge>;
}
