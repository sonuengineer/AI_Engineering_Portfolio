import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, post } from "../api/client";
import type { Run } from "../api/types";
import { hasRole, useAuth } from "../components/auth";
import { useAsync } from "../components/useAsync";
import { Button, Card, EmptyState, ErrorBanner, Loading, StatusBadge } from "../components/ui";

export const DEMO_GOAL = "Investigate why purchases are declining among our top ten customers over the last 6 months";

export function Investigations() {
  const { me } = useAuth();
  const runs = useAsync(() => api<Run[]>("/workflows"));
  const [goal, setGoal] = useState(DEMO_GOAL);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const nav = useNavigate();

  const start = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(undefined);
    try { const r = await post<Run>("/workflows", { goal }); nav(`/investigations/${r.id}`); }
    catch (err) { setError(err); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Agent investigations</h1>
      {hasRole(me, "analyst") && (
        <Card title="Start an investigation">
          <form onSubmit={start} className="space-y-3">
            <label htmlFor="goal" className="block text-sm text-slate-600">
              A supervisor agent plans the work; data, research, analysis, report and action agents execute it with checkpoints. Outbound emails always wait for human approval.
            </label>
            <textarea id="goal" rows={2} value={goal} onChange={(e) => setGoal(e.target.value)} minLength={10} maxLength={2000} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            <ErrorBanner error={error} />
            <Button type="submit" busy={busy}>Run investigation</Button>
          </form>
        </Card>
      )}
      <Card title="Workflow history">
        {runs.loading ? <Loading /> : runs.error ? <ErrorBanner error={runs.error} onRetry={() => void runs.reload()} /> :
          !runs.data?.length ? <EmptyState title="No investigations yet">Start one above to see agent activity.</EmptyState> :
          <ul className="divide-y divide-slate-100">
            {runs.data.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <Link to={`/investigations/${r.id}`} className="max-w-xl truncate text-brand-700 hover:underline">{r.goal}</Link>
                <span className="flex items-center gap-3 text-xs text-slate-500">
                  {new Date(r.created_at).toLocaleString()} <span>{r.tokens_used.toLocaleString()} tok</span> <StatusBadge status={r.status} />
                </span>
              </li>
            ))}
          </ul>}
      </Card>
    </div>
  );
}
