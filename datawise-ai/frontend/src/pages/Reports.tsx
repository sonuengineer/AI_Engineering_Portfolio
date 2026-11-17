import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { AnswerPanel } from "../components/AnswerPanel";
import { Empty, ErrorBox, Loading } from "../components/Feedback";
import type { AskResponse, SavedReport } from "../types";

export function ReportsPage() {
  const [reports, setReports] = useState<SavedReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState<number | null>(null);
  const [result, setResult] = useState<{ report: SavedReport; res: AskResponse } | null>(null);

  const load = useCallback(() => {
    api.reports().then(setReports).catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Failed to load reports"));
  }, []);
  useEffect(load, [load]);

  async function rerun(r: SavedReport) {
    setRunning(r.id);
    setError(null);
    try {
      setResult({ report: r, res: await api.runReport(r.id) });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Run failed");
    } finally {
      setRunning(null);
    }
  }

  async function remove(r: SavedReport) {
    if (!window.confirm(`Delete report "${r.name}"?`)) return;
    await api.deleteReport(r.id).catch(() => setError("Delete failed"));
    if (result?.report.id === r.id) setResult(null);
    load();
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Saved reports</h1>
      {error ? <ErrorBox message={error} /> : null}
      {!reports ? <Loading label="Loading reports" /> : reports.length === 0 ? (
        <Empty>No saved reports yet. Ask a question and use "Save report".</Empty>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {reports.map((r) => (
            <li key={r.id} className="rounded-md border border-slate-200 bg-white p-3">
              <p className="font-medium">{r.name}</p>
              <p className="text-sm text-slate-500">{r.question}</p>
              <p className="mt-1 text-xs text-slate-400">
                metrics: {r.plan.metrics.join(", ")}{r.plan.dimensions.length ? ` | by ${r.plan.dimensions.join(", ")}` : ""}
              </p>
              <div className="mt-2 flex gap-2">
                <button type="button" onClick={() => void rerun(r)} disabled={running === r.id}
                  className="focus-ring rounded bg-teal-700 px-3 py-1 text-sm text-white hover:bg-teal-800 disabled:opacity-50">
                  {running === r.id ? "Running" : "Re-run"}
                </button>
                <button type="button" onClick={() => void remove(r)}
                  className="focus-ring rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100" aria-label={`Delete report ${r.name}`}>
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {result ? (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold text-slate-600">Result: {result.report.name}</h2>
          <AnswerPanel result={result.res} question={result.report.question} />
        </div>
      ) : null}
    </div>
  );
}
