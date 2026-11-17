import { useState } from "react";
import { post } from "../api/client";
import type { Approval } from "../api/types";
import { hasRole, useAuth } from "./auth";
import { Button, ErrorBanner, StatusBadge } from "./ui";

export function ApprovalCard({ approval, onChange }: { approval: Approval; onChange: (a: Approval) => void }) {
  const { me } = useAuth();
  const [subject, setSubject] = useState(approval.payload.subject);
  const [body, setBody] = useState(approval.payload.body);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<unknown>();
  const canDecide = hasRole(me, "manager") && approval.status === "pending";

  const decide = async (kind: "approve" | "reject") => {
    setBusy(kind); setError(undefined);
    try {
      const payload = kind === "approve"
        ? { note: note || null, subject: subject !== approval.payload.subject ? subject : null, body: body !== approval.payload.body ? body : null }
        : { note: note || null };
      onChange(await post<Approval>(`/approvals/${approval.id}/${kind}`, payload));
    } catch (e) { setError(e); } finally { setBusy(null); }
  };

  return (
    <article className="space-y-2 rounded-lg border border-slate-200 bg-white p-4" aria-label={`Approval for ${approval.payload.customer_name ?? approval.payload.to}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Send email to {approval.payload.customer_name} <span className="font-normal text-slate-500">&lt;{approval.payload.to}&gt;</span></h3>
        <StatusBadge status={approval.status} />
      </div>
      {approval.rationale && <p className="text-xs text-slate-500">Why: {approval.rationale}</p>}
      <label className="block text-xs font-medium text-slate-600">Subject
        <input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!canDecide} maxLength={200} className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm disabled:bg-slate-50" />
      </label>
      <label className="block text-xs font-medium text-slate-600">Body
        <textarea value={body} onChange={(e) => setBody(e.target.value)} disabled={!canDecide} rows={7} maxLength={4000} className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm disabled:bg-slate-50" />
      </label>
      {canDecide && (
        <>
          <label className="block text-xs font-medium text-slate-600">Decision note (optional)
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm" />
          </label>
          <div className="flex gap-2">
            <Button onClick={() => void decide("approve")} busy={busy === "approve"} disabled={busy !== null}>Approve and send</Button>
            <Button variant="secondary" onClick={() => void decide("reject")} busy={busy === "reject"} disabled={busy !== null}>Reject</Button>
          </div>
        </>
      )}
      {!canDecide && approval.status === "pending" && <p className="text-xs text-slate-500">Only managers or admins can approve external communication.</p>}
      {approval.status === "executed" && <p className="text-xs text-emerald-700">Delivered to the local outbox connector (no real email is sent in the demo).</p>}
      <ErrorBanner error={error} />
    </article>
  );
}
