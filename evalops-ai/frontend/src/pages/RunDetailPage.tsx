import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadFile } from "../api/client";
import { TERMINAL_STATUSES, type CaseResult, type Run } from "../api/types";
import { DeterministicBanner, StatusPill } from "../components/Badge";
import { DataState, ErrorBox } from "../components/DataState";
import { PageTitle, btn, link } from "../components/Layout";
import { MetricCard, StatCard } from "../components/MetricCard";
import { ProgressBar } from "../components/ProgressBar";
import { dateTime, ms, num, pct, shortHash, usd } from "../lib/format";
import { useApi } from "../lib/useApi";
import { useRunPolling } from "../lib/useRunPolling";
import { CaseTable } from "./run/CaseTable";
import { RunCharts } from "./run/RunCharts";

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const poll = useRunPolling(runId);
  return (
    <DataState data={poll.run} error={poll.error} loading={poll.loading} reload={poll.reload} loadingLabel="Loading run">
      {(run) => <RunView run={run} />}
    </DataState>
  );
}

function RunView({ run }: { run: Run }) {
  const done = TERMINAL_STATUSES.includes(run.status);
  return (
    <>
      <p className="mb-1 text-sm">
        <Link to={`/projects/${run.project_id}`} className={link}>
          Back to project
        </Link>
      </p>
      <div className="flex flex-wrap items-start gap-2">
        <div className="mr-auto min-w-0">
          <PageTitle sub={<span className="font-mono text-xs">{run.id}</span>}>{run.label || "Untitled run"}</PageTitle>
        </div>
        <StatusPill status={run.status} />
      </div>
      {run.is_deterministic_provider && (
        <div className="mb-4">
          <DeterministicBanner />
        </div>
      )}
      <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-slate-200 bg-white p-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
        <Meta label="Target" value={`${run.target_name ?? "--"} (${run.target_kind ?? "?"})`} />
        <Meta label="Provider / model" value={`${run.provider ?? "--"} / ${run.model ?? "--"}`} mono />
        <Meta label="Dataset hash" value={shortHash(run.dataset_hash, 12)} mono title={run.dataset_hash ?? undefined} />
        <Meta label="Seed" value={String(run.seed)} mono />
        <Meta label="Git SHA" value={run.git_sha ? shortHash(run.git_sha, 10) : "--"} mono />
        <Meta label="Created" value={dateTime(run.created_at)} />
      </dl>
      {!done && <ProgressBar done={run.progress_done} total={run.progress_total} status={run.status} />}
      {run.status === "failed" && <ErrorBox error={new Error(`Run failed: ${run.error ?? "unknown error"}`)} />}
      {done && run.status !== "cancelled" && <RunResults run={run} />}
    </>
  );
}

function Meta({ label, value, mono, title }: { label: string; value: string; mono?: boolean; title?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs uppercase text-slate-600">{label}</dt>
      <dd className={`break-words ${mono ? "font-mono text-xs" : ""}`} title={title}>
        {value}
      </dd>
    </div>
  );
}

function RunResults({ run }: { run: Run }) {
  const all = useApi((signal) => api<CaseResult[]>(`/api/v1/runs/${run.id}/results`, { signal }), [run.id]);
  const [dlError, setDlError] = useState<unknown>(null);
  const s = run.summary;

  const download = async (kind: "report.json" | "report.md" | "results.csv") => {
    setDlError(null);
    try {
      const ext = kind.split(".")[1];
      await downloadFile(`/api/v1/runs/${run.id}/${kind}`, `evalops-run-${run.id}.${ext}`);
    } catch (e) {
      setDlError(e);
    }
  };

  const skipReason = (metric: string, cases: CaseResult[]) =>
    cases.flatMap((c) => c.scores).find((sc) => sc.metric === metric && sc.status === "skipped")?.explanation ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Download reports">
        <button type="button" className={btn} onClick={() => download("report.json")}>
          Download JSON
        </button>
        <button type="button" className={btn} onClick={() => download("report.md")}>
          Download Markdown
        </button>
        <button type="button" className={btn} onClick={() => download("results.csv")}>
          Download CSV
        </button>
      </div>
      {dlError !== null && <ErrorBox error={dlError} />}

      {s ? (
        <>
          <section aria-label="Operational metrics">
            <h2 className="mb-2 text-lg font-semibold">Operational</h2>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
              <StatCard label="Overall pass rate" value={pct(s.overall_pass_rate)} hint={`${s.cases_passed} / ${s.cases_judged} judged cases`} />
              <StatCard label="Error rate" value={pct(s.error_rate)} hint={`${s.error_count} / ${s.case_count} cases`} />
              <StatCard label="Latency mean" value={ms(s.latency_ms.mean)} />
              <StatCard label="Latency p50 / p95" value={`${ms(s.latency_ms.p50)} / ${ms(s.latency_ms.p95)}`} />
              <StatCard label="Tokens (in / out)" value={`${s.tokens.input} / ${s.tokens.output}`} hint={`${s.tokens.total} total`} />
              <StatCard label="Cost" value={usd(s.cost_usd)} />
              <StatCard
                label="Throughput"
                value={s.throughput_cases_per_sec !== null ? `${num(s.throughput_cases_per_sec, 1)} cases/s` : "--"}
                hint={s.wall_seconds !== null ? `wall ${num(s.wall_seconds, 2)} s` : undefined}
              />
            </div>
          </section>
          <section aria-label="Quality metrics">
            <h2 className="mb-2 text-lg font-semibold">Metrics</h2>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(s.metrics)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([name, m]) => (
                <MetricCard key={name} name={name} metric={m} skipReason={all.data ? skipReason(name, all.data) : null} />
              ))}
            </div>
            {Object.values(s.metrics).some((m) => m.is_estimate) && (
              <p className="mt-2 text-xs text-slate-600">
                Metrics marked "estimate" come from an LLM judge; they are reported but never decide pass/fail.
              </p>
            )}
          </section>
        </>
      ) : (
        <p className="text-sm text-slate-600">No summary recorded for this run.</p>
      )}

      <DataState {...all} loadingLabel="Loading case results">
        {(cases) => (
          <>
            {s && (
              <section aria-label="Charts">
                <h2 className="mb-2 text-lg font-semibold">Charts</h2>
                <RunCharts summary={s} cases={cases} />
              </section>
            )}
            <CaseTable
              runId={run.id}
              metrics={Object.keys(s?.metrics ?? {})}
              tags={[...new Set(cases.flatMap((c) => c.tags))].sort()}
            />
          </>
        )}
      </DataState>
    </div>
  );
}
