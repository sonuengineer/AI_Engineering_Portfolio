import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { CompareResult, Run } from "../api/types";
import { Badge } from "../components/Badge";
import { MetricDeltaTable, OperationalTable } from "../components/CompareTable";
import { DataState, ErrorBox } from "../components/DataState";
import { PageTitle, btn, input, link } from "../components/Layout";
import { shortHash } from "../lib/format";
import { useApi } from "../lib/useApi";

export function ComparePage() {
  const [params, setParams] = useSearchParams();
  const baseline = params.get("baseline") ?? "";
  const candidate = params.get("candidate") ?? "";
  const tolerance = params.get("tolerance") ?? "0.02";
  const [tolDraft, setTolDraft] = useState(tolerance);

  const state = useApi(
    (signal) => api<CompareResult>("/api/v1/compare", { query: { baseline, candidate, tolerance }, signal }),
    [baseline, candidate, tolerance],
  );

  if (!baseline || !candidate) {
    return (
      <>
        <PageTitle>Compare runs</PageTitle>
        <ErrorBox error={new Error("Pick two runs from a project's Runs tab to compare (baseline and candidate query params).")} />
      </>
    );
  }

  const tolValid = tolDraft !== "" && Number(tolDraft) >= 0 && Number(tolDraft) <= 1;

  return (
    <>
      <PageTitle>Compare runs</PageTitle>
      <form
        className="mb-4 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (tolValid) setParams({ baseline, candidate, tolerance: String(Number(tolDraft)) });
        }}
      >
        <div>
          <label htmlFor="tol" className="block text-xs font-medium text-slate-700">
            Tolerance (absolute pass-rate drop, 0-1)
          </label>
          <input
            id="tol"
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={tolDraft}
            onChange={(e) => setTolDraft(e.target.value)}
            className={`${input} mt-1 w-32`}
          />
        </div>
        <button type="submit" className={btn} disabled={!tolValid}>
          Apply
        </button>
        <button
          type="button"
          className={btn}
          onClick={() => setParams({ baseline: candidate, candidate: baseline, tolerance })}
        >
          Swap baseline / candidate
        </button>
      </form>
      <DataState {...state} loadingLabel="Comparing runs">
        {(c) => <CompareView c={c} />}
      </DataState>
    </>
  );
}

function RunRef({ role, run }: { role: string; run: Run }) {
  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-3 text-sm">
      <p className="text-xs uppercase text-slate-600">{role}</p>
      <Link to={`/runs/${run.id}`} className={`${link} font-medium`}>
        {run.label || run.id.slice(0, 8)}
      </Link>
      <p className="text-xs text-slate-600">
        {run.target_name} | <span className="font-mono">{run.provider}</span> | dataset {shortHash(run.dataset_hash, 8)}
      </p>
      {run.is_deterministic_provider && (
        <p className="mt-1">
          <Badge tone="amber">deterministic / scripted -- not a real LLM</Badge>
        </p>
      )}
    </div>
  );
}

function CaseList({ title, ids, tone }: { title: string; ids: string[]; tone: "red" | "green" | "gray" }) {
  return (
    <section aria-label={title} className="rounded-lg border border-slate-200 bg-white p-3">
      <h3 className="mb-2 text-sm font-semibold">
        {title} <span className="text-slate-600">({ids.length})</span>
      </h3>
      {ids.length === 0 ? (
        <p className="text-xs text-slate-600">None</p>
      ) : (
        <ul className="flex flex-wrap gap-1">
          {ids.map((id) => (
            <li key={id}>
              <Badge tone={tone}>{id}</Badge>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function CompareView({ c }: { c: CompareResult }) {
  const hasEstimate = c.metrics.some((m) => m.is_estimate);
  return (
    <div className="space-y-5">
      <div className="grid gap-2 sm:grid-cols-2">
        <RunRef role="Baseline" run={c.baseline} />
        <RunRef role="Candidate" run={c.candidate} />
      </div>
      {!c.same_dataset && (
        <div role="alert" className="rounded-md border-2 border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Warning: the two runs used different dataset contents (hashes differ). Deltas may not be comparable.
        </div>
      )}
      <div
        role="status"
        className={`rounded-md p-3 text-sm font-medium ${
          c.has_regression ? "border border-red-300 bg-red-50 text-red-900" : "border border-green-300 bg-green-50 text-green-900"
        }`}
      >
        {c.has_regression ? `Regression detected in: ${c.regressions.join(", ")}` : "No regressions beyond tolerance."}
      </div>
      <section aria-label="Metric deltas">
        <h2 className="mb-2 text-lg font-semibold">Metrics</h2>
        <MetricDeltaTable rows={c.metrics} />
        {hasEstimate && (
          <p className="mt-2 text-xs text-slate-600">
            Estimate metrics come from an LLM judge: they are shown for context but are non-gating and never count as a regression.
          </p>
        )}
      </section>
      <section aria-label="Operational deltas">
        <h2 className="mb-2 text-lg font-semibold">Operational</h2>
        <OperationalTable rows={c.operational} />
      </section>
      <section aria-label="Case changes">
        <h2 className="mb-2 text-lg font-semibold">Cases</h2>
        <div className="grid gap-2 md:grid-cols-3">
          <CaseList title="Newly failing" ids={c.cases.newly_failing} tone="red" />
          <CaseList title="Newly passing" ids={c.cases.newly_passing} tone="green" />
          <CaseList title="Still failing" ids={c.cases.still_failing} tone="gray" />
        </div>
        {(c.cases.only_in_baseline.length > 0 || c.cases.only_in_candidate.length > 0) && (
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            <CaseList title="Only in baseline" ids={c.cases.only_in_baseline} tone="gray" />
            <CaseList title="Only in candidate" ids={c.cases.only_in_candidate} tone="gray" />
          </div>
        )}
      </section>
    </div>
  );
}
