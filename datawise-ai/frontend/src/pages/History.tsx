import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { Empty, ErrorBox, Loading } from "../components/Feedback";
import type { HistoryItem } from "../types";

export function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.history().then(setItems).catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Failed to load history"));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!items) return <Loading label="Loading history" />;
  return (
    <div className="space-y-3">
      <h1 className="text-lg font-semibold">Query history <span className="text-sm font-normal text-slate-500">(your organization)</span></h1>
      {items.length === 0 ? <Empty>No questions asked yet.</Empty> : (
        <ul className="space-y-2">
          {items.map((h) => (
            <li key={h.id} className="rounded-md border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="font-semibold text-slate-700">{h.status}</span>
                <span>{new Date(h.created_at).toLocaleString()}</span>
                <span>{h.row_count} rows</span>
                <span>{h.latency_ms} ms</span>
                <span>provider: {h.provider}</span>
              </div>
              <p className="mt-1 text-sm">{h.question}</p>
              {h.sql ? (
                <details className="mt-1 text-xs">
                  <summary className="cursor-pointer text-slate-500">SQL</summary>
                  <pre className="mt-1 overflow-x-auto rounded bg-slate-900 p-2 text-slate-100">{h.sql}</pre>
                </details>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
