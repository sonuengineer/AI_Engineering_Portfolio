import { useState } from "react";
import type { AskResponse } from "../types";
import { ProviderBadge } from "./ProviderBadge";
import { ResultChart } from "./ResultChart";
import { ResultTable } from "./ResultTable";
import { SqlBlock } from "./SqlBlock";
import { Empty } from "./Feedback";

interface Props {
  result: AskResponse;
  question: string;
  onClarify?: (option: string) => void;
  onSave?: (name: string) => Promise<void>;
}

const STATUS_STYLE: Record<string, string> = {
  answered: "bg-emerald-100 text-emerald-800",
  needs_clarification: "bg-sky-100 text-sky-800",
  rejected: "bg-red-100 text-red-800",
};

export function AnswerPanel({ result, question, onClarify, onSave }: Props) {
  const [saveName, setSaveName] = useState(question.slice(0, 80));
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const highlight = result.insight_provenance.flatMap((p) => (p.row_indexes.length <= 3 ? p.row_indexes : []));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!onSave) return;
    setSaveState("saving");
    try {
      await onSave(saveName);
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  }

  return (
    <section aria-label="Answer" className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLE[result.status] ?? ""}`} data-testid="status">
          {result.status.replace("_", " ")}
        </span>
        <ProviderBadge provider={result.provider} model={result.model} />
        <span className="text-xs text-slate-500">{result.latency_ms} ms</span>
      </div>

      {result.status === "rejected" ? (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <p className="font-medium">Request rejected</p>
          <p>{result.rejection_reason}</p>
        </div>
      ) : null}

      {result.status === "needs_clarification" && result.clarification ? (
        <div className="rounded-md border border-sky-200 bg-sky-50 p-3">
          <p className="text-sm text-sky-900">{result.clarification.question}</p>
          {result.clarification.options.length ? (
            <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Clarification options">
              {result.clarification.options.map((o) => (
                <button key={o} type="button" onClick={() => onClarify?.(o)}
                  className="focus-ring rounded-full border border-sky-300 bg-white px-3 py-1 text-sm text-sky-800 hover:bg-sky-100">
                  {o}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {result.insight ? (
        <div className="rounded-md border border-teal-200 bg-teal-50 p-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-teal-700">Insight (computed from the rows below)</h3>
          <p className="mt-1 text-sm text-teal-950" data-testid="insight">{result.insight}</p>
          {result.insight_provenance.length ? (
            <details className="mt-2 text-xs text-teal-800">
              <summary className="cursor-pointer">Provenance</summary>
              <ul className="mt-1 list-disc pl-5">
                {result.insight_provenance.map((p, i) => (
                  <li key={i}>
                    {p.note}: columns [{p.columns.join(", ")}], rows [
                    {p.row_indexes.length > 12 ? `${p.row_indexes.length} rows` : p.row_indexes.join(", ")}]
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}

      {result.plan?.assumptions.length ? (
        <ul className="list-disc pl-5 text-xs text-slate-500" aria-label="Assumptions">
          {result.plan.assumptions.map((a) => <li key={a}>{a}</li>)}
        </ul>
      ) : null}

      {result.status === "answered" && result.chart ? (
        <ResultChart spec={result.chart} columns={result.columns} rows={result.rows} />
      ) : null}

      {result.status === "answered" ? (
        result.rows.length ? (
          <ResultTable columns={result.columns} rows={result.rows} highlight={highlight} />
        ) : (
          <Empty>The query ran successfully but returned no rows.</Empty>
        )
      ) : null}

      {result.sql ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <h3 className="font-medium text-slate-700">Generated SQL</h3>
            <span className={`rounded px-2 py-0.5 text-xs ${result.validation.ok ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
              {result.validation.ok ? "Validation passed" : "Validation failed"}
            </span>
          </div>
          {result.validation.issues.length ? (
            <ul className="list-disc pl-5 text-xs text-red-700" aria-label="Validation issues">
              {result.validation.issues.map((i) => <li key={i}>{i}</li>)}
            </ul>
          ) : null}
          <SqlBlock sql={result.sql} />
        </div>
      ) : null}

      {result.status === "answered" && result.plan && onSave ? (
        <form onSubmit={save} className="flex flex-wrap items-end gap-2 border-t border-slate-100 pt-3">
          <label className="flex grow flex-col text-xs text-slate-600">
            Report name
            <input value={saveName} onChange={(e) => setSaveName(e.target.value)} required maxLength={200}
              className="focus-ring mt-1 rounded border border-slate-300 px-2 py-1 text-sm" />
          </label>
          <button type="submit" disabled={saveState === "saving"}
            className="focus-ring rounded bg-slate-800 px-3 py-1.5 text-sm text-white hover:bg-slate-700 disabled:opacity-50">
            {saveState === "saved" ? "Saved" : saveState === "saving" ? "Saving" : "Save report"}
          </button>
          {saveState === "error" ? <span className="text-xs text-red-700">Could not save.</span> : null}
        </form>
      ) : null}
    </section>
  );
}
