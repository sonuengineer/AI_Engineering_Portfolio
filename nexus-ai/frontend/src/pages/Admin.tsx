import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { AuditRow, MemoryItem, ToolInfo, UsageRow } from "../api/types";
import { useAsync } from "../components/useAsync";
import { Badge, Button, Card, EmptyState, ErrorBanner, Loading } from "../components/ui";

export function Admin() {
  const usage = useAsync(() => api<{ by_purpose: UsageRow[]; note: string }>("/admin/usage"));
  const audit = useAsync(() => api<AuditRow[]>("/admin/audit?limit=60"));
  const tools = useAsync(() => api<ToolInfo[]>("/tools"));
  const outbox = useAsync(() => api<{ id: string; to: string; subject: string; created_at: string }[]>("/admin/outbox"));
  const memory = useAsync(() => api<MemoryItem[]>("/memory"));
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [memErr, setMemErr] = useState<unknown>();

  const saveMemory = async (e: FormEvent) => {
    e.preventDefault(); setMemErr(undefined);
    try { await api("/memory", { method: "PUT", body: JSON.stringify({ key, value }) }); setKey(""); setValue(""); await memory.reload(true); }
    catch (err) { setMemErr(err); }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Admin and observability</h1>
      <Card title="Model usage and estimated cost">
        {usage.loading ? <Loading /> : usage.error ? <ErrorBanner error={usage.error} /> : !usage.data?.by_purpose.length ? <EmptyState title="No model calls yet" /> :
          <>
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs uppercase text-slate-500"><th className="py-1">Purpose</th><th>Provider/model</th><th>Calls</th><th>Tokens in/out</th><th>Est. cost</th><th>Avg latency</th></tr></thead>
              <tbody>{usage.data.by_purpose.map((u) => (
                <tr key={u.purpose + u.model} className="border-t border-slate-100"><td className="py-1">{u.purpose}</td><td>{u.provider}/{u.model}</td><td>{u.calls}</td>
                  <td>{u.input_tokens.toLocaleString()} / {u.output_tokens.toLocaleString()}</td><td>${u.estimated_cost_usd.toFixed(4)}</td><td>{u.avg_latency_ms} ms</td></tr>))}</tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">{usage.data.note}</p>
          </>}
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Tool registry (typed, permissioned)">
          {tools.loading ? <Loading /> : <ul className="space-y-2 text-sm">{(tools.data ?? []).map((t) => (
            <li key={t.name}><code className="font-semibold">{t.name}</code> <Badge tone={t.side_effect === "read" ? "green" : t.side_effect === "write" ? "amber" : "red"}>{t.side_effect}</Badge>
              {t.requires_approval && <Badge tone="violet">approval required</Badge>} {t.mcp_exposed && <Badge tone="blue">MCP</Badge>}
              <span className="block text-xs text-slate-500">{t.description} (min role: {t.min_role})</span></li>))}</ul>}
        </Card>
        <Card title="Outbox (local email connector)">
          {outbox.loading ? <Loading /> : !outbox.data?.length ? <EmptyState title="Nothing sent yet">Approved emails appear here.</EmptyState> :
            <ul className="space-y-1 text-sm">{outbox.data.map((m) => <li key={m.id}>{new Date(m.created_at).toLocaleString()} -- <strong>{m.to}</strong>: {m.subject}</li>)}</ul>}
        </Card>
      </div>
      <Card title="Your long-term memory (explicit and deletable)">
        <form onSubmit={saveMemory} className="mb-3 flex flex-wrap gap-2">
          <label className="sr-only" htmlFor="mk">Key</label>
          <input id="mk" placeholder="key, e.g. preferred_region" value={key} onChange={(e) => setKey(e.target.value)} required pattern="[a-zA-Z0-9_ .\-]+" className="rounded border border-slate-300 px-2 py-1 text-sm" />
          <label className="sr-only" htmlFor="mv">Value</label>
          <input id="mv" placeholder="value" value={value} onChange={(e) => setValue(e.target.value)} required className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm" />
          <Button type="submit">Save</Button>
        </form>
        <ErrorBanner error={memErr} />
        {!memory.data?.length ? <p className="text-sm text-slate-500">No stored preferences. Memory is only written when you add it here.</p> :
          <ul className="space-y-1 text-sm">{memory.data.map((m) => (
            <li key={m.id} className="flex items-center justify-between"><span><strong>{m.key}</strong>: {m.value}</span>
              <Button variant="ghost" onClick={() => void api(`/memory/${m.id}`, { method: "DELETE" }).then(() => memory.reload(true))}>Delete</Button></li>))}</ul>}
      </Card>
      <Card title="Audit trail (latest 60)">
        {audit.loading ? <Loading /> : audit.error ? <ErrorBanner error={audit.error} /> :
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-white"><tr className="text-left uppercase text-slate-500"><th className="py-1">Time</th><th>Action</th><th>Outcome</th><th>Target</th><th>Request</th></tr></thead>
              <tbody>{(audit.data ?? []).map((a) => (
                <tr key={a.id} className="border-t border-slate-100"><td className="py-1 pr-2">{new Date(a.created_at).toLocaleTimeString()}</td><td><code>{a.action}</code></td>
                  <td><Badge tone={a.outcome === "success" ? "green" : "red"}>{a.outcome}</Badge></td><td>{a.target_type ?? ""}</td><td className="text-slate-400">{a.request_id?.slice(0, 8)}</td></tr>))}</tbody>
            </table>
          </div>}
      </Card>
    </div>
  );
}
