import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Approval } from "../api/types";
import { ApprovalCard } from "../components/ApprovalCard";
import { useAsync } from "../components/useAsync";
import { EmptyState, ErrorBanner, Loading, cx } from "../components/ui";

const FILTERS = ["pending", "executed", "rejected", "all"] as const;

export function Approvals() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("pending");
  const list = useAsync(() => api<Approval[]>(`/approvals${filter === "all" ? "" : `?status=${filter}`}`), [filter]);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Approval queue</h1>
      <p className="text-sm text-slate-600">External communication and sensitive actions proposed by agents wait here. Approving executes the action exactly once (idempotency key).</p>
      <div role="tablist" aria-label="Filter" className="flex gap-1">
        {FILTERS.map((f) => (
          <button key={f} role="tab" aria-selected={filter === f} onClick={() => setFilter(f)}
            className={cx("rounded-md px-3 py-1.5 text-sm", filter === f ? "bg-brand-50 font-medium text-brand-700" : "text-slate-600 hover:bg-slate-100")}>{f}</button>
        ))}
      </div>
      {list.loading ? <Loading /> : list.error ? <ErrorBanner error={list.error} onRetry={() => void list.reload()} /> :
        !list.data?.length ? <EmptyState title={`No ${filter === "all" ? "" : filter} approvals`}>Run an <Link className="text-brand-700 underline" to="/investigations">investigation</Link> to generate follow-up drafts.</EmptyState> :
        <div className="grid gap-4 lg:grid-cols-2">
          {list.data.map((a) => <ApprovalCard key={a.id} approval={a} onChange={() => void list.reload(true)} />)}
        </div>}
    </div>
  );
}
