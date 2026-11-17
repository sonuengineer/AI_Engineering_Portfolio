import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, post } from "../api/client";
import type { Approval, DecliningCustomer, RunDetail as RunDetailT } from "../api/types";
import { ApprovalCard } from "../components/ApprovalCard";
import { hasRole, useAuth } from "../components/auth";
import { Markdown } from "../components/Markdown";
import { useAsync } from "../components/useAsync";
import { Badge, Button, Card, ErrorBanner, Loading, StatusBadge } from "../components/ui";

const COLORS = ["#2f5bea", "#e11d48", "#059669", "#d97706", "#7c3aed", "#0891b2", "#be185d", "#4d7c0f"];
const ACTIVE = new Set(["running"]);

function DeclineChart({ customers }: { customers: DecliningCustomer[] }) {
  const months = Array.from(new Set(customers.flatMap((c) => c.monthly.map((m) => m.month)))).sort();
  const data = months.map((m) => {
    const row: Record<string, string | number> = { month: m };
    for (const c of customers) row[c.name] = Math.round(c.monthly.find((x) => x.month === m)?.revenue ?? 0);
    return row;
  });
  return (
    <figure aria-label="Monthly revenue of declining customers">
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ left: 10, right: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="month" fontSize={11} />
            <YAxis fontSize={11} tickFormatter={(v: number) => `${Math.round(v / 1000)}k`} />
            <Tooltip formatter={(v) => Number(v).toLocaleString()} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {customers.map((c, i) => <Line key={c.customer_id} type="monotone" dataKey={c.name} stroke={COLORS[i % COLORS.length]} dot={false} strokeWidth={2} isAnimationActive={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-slate-500">Completed-order revenue per month from ERP records (synthetic demo data).</figcaption>
    </figure>
  );
}

export function RunDetail() {
  const { id = "" } = useParams();
  const { me } = useAuth();
  const run = useAsync(() => api<RunDetailT>(`/workflows/${id}`), [id]);
  const status = run.data?.status;
  useEffect(() => {
    if (!status || !ACTIVE.has(status)) return;
    const t = setInterval(() => void run.reload(true), 1200);
    return () => clearInterval(t);
  }, [status, run]);

  if (run.loading) return <Loading label="Loading investigation" />;
  if (run.error || !run.data) return <ErrorBanner error={run.error} onRetry={() => void run.reload()} />;
  const r = run.data;
  const analysis = r.report?.analysis;
  const updateApproval = (a: Approval) => { run.setData({ ...r, approvals: r.approvals.map((x) => (x.id === a.id ? a : x)) }); void run.reload(true); };
  const resume = async () => { await post(`/workflows/${r.id}/resume`); await run.reload(true); };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/investigations" className="text-sm text-brand-700 hover:underline">&larr; All investigations</Link>
          <h1 className="mt-1 text-xl font-semibold">{r.goal}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-500">
            <StatusBadge status={r.status} /> Tokens {r.tokens_used.toLocaleString()} / budget {r.token_budget.toLocaleString()}
          </p>
        </div>
        {(r.status === "failed" || r.status === "interrupted") && hasRole(me, "analyst") && r.plan.length > 0 && <Button onClick={() => void resume()}>Resume from checkpoint</Button>}
      </div>
      {r.error && <ErrorBanner error={{ message: r.error }} />}

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <Card title="Agent activity">
          <ol className="space-y-3" aria-live="polite">
            {r.steps.map((s) => (
              <li key={s.id} className="rounded-md border border-slate-100 p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{s.seq}. {s.name.replace("_", " ")}</span>
                  <StatusBadge status={s.status} />
                </div>
                {s.attempts > 1 && <p className="text-xs text-amber-700">Retried: {s.attempts} attempts</p>}
                {s.error && <p className="text-xs text-rose-700">{s.error}</p>}
                <ul className="mt-1 space-y-0.5">
                  {s.tool_calls.map((t, i) => <li key={i} className="truncate text-xs text-slate-500" title={JSON.stringify(t.args)}><code>{t.tool}</code> -- {t.summary}</li>)}
                </ul>
              </li>
            ))}
            {ACTIVE.has(r.status) && <li className="text-xs text-slate-500"><Loading label="Agents working" /></li>}
          </ol>
        </Card>

        <div className="space-y-6">
          {r.report?.declining && r.report.declining.length > 0 && <Card title="Revenue trend: customers flagged as declining"><DeclineChart customers={r.report.declining} /></Card>}
          {analysis && (
            <Card title="Findings: evidence vs hypotheses">
              <p className="mb-4 text-sm text-slate-700">{analysis.summary}</p>
              <div className="space-y-4">
                {analysis.findings.map((f) => (
                  <article key={f.customer_id} className="rounded-lg border border-slate-200 p-3">
                    <h3 className="font-semibold">{f.customer_name}</h3>
                    <h4 className="mt-2 text-xs font-semibold uppercase text-emerald-700">Evidence (from records)</h4>
                    <ul className="mt-1 space-y-1 text-sm">{f.evidence.map((e, i) => <li key={i}>{e.statement} <Badge>{e.source.split(":")[0]}</Badge></li>)}</ul>
                    <h4 className="mt-3 text-xs font-semibold uppercase text-violet-700">Hypotheses (inferences -- validate before acting)</h4>
                    <ul className="mt-1 space-y-1 text-sm">{f.hypotheses.map((h, i) => (
                      <li key={i}><Badge tone={h.confidence === "high" ? "green" : h.confidence === "medium" ? "amber" : "slate"}>{h.confidence}</Badge> {h.statement}
                        <span className="text-xs text-slate-500"> ({h.supporting_sources.length} supporting source{h.supporting_sources.length === 1 ? "" : "s"})</span></li>))}</ul>
                    <p className="mt-2 text-sm text-brand-700">Recommended: {f.recommended_action}</p>
                  </article>
                ))}
              </div>
            </Card>
          )}
          {r.approvals.length > 0 && (
            <Card title={`Follow-up drafts awaiting human approval (${r.approvals.filter((a) => a.status === "pending").length} pending)`}>
              <div className="space-y-3">{r.approvals.map((a) => <ApprovalCard key={a.id} approval={a} onChange={updateApproval} />)}</div>
            </Card>
          )}
          {r.report && (
            <Card title="Full report">
              <details>
                <summary className="cursor-pointer text-sm font-medium text-brand-700">Show the generated markdown report</summary>
                <div className="mt-3"><Markdown source={r.report.markdown} /></div>
              </details>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
