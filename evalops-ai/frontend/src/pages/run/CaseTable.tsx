import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { CaseResult } from "../../api/types";
import { Badge, PassPill } from "../../components/Badge";
import { DataState } from "../../components/DataState";
import { btn, input, link } from "../../components/Layout";
import { ms, num, usd } from "../../lib/format";
import { useApi } from "../../lib/useApi";

type Mode = "all" | "failed" | "metric" | "tag";

export function CaseTable({ runId, metrics, tags }: { runId: string; metrics: string[]; tags: string[] }) {
  const [mode, setMode] = useState<Mode>("all");
  const [metric, setMetric] = useState(metrics[0] ?? "");
  const [tag, setTag] = useState(tags[0] ?? "");
  const [open, setOpen] = useState<string | null>(null);

  const query = {
    failed_only: mode === "failed" ? true : undefined,
    metric: mode === "metric" ? metric : undefined,
    tag: mode === "tag" ? tag : undefined,
  };
  const results = useApi(
    (signal) => api<CaseResult[]>(`/api/v1/runs/${runId}/results`, { query, signal }),
    [runId, mode, metric, tag],
  );

  return (
    <section aria-label="Per-case results">
      <h2 className="mb-2 text-lg font-semibold">Cases</h2>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="case-filter" className="block text-xs font-medium text-slate-700">
            Show
          </label>
          <select id="case-filter" value={mode} onChange={(e) => setMode(e.target.value as Mode)} className={`${input} mt-1 w-48`}>
            <option value="all">All cases</option>
            <option value="failed">Failures only</option>
            <option value="metric">Failing a metric</option>
            <option value="tag">By tag</option>
          </select>
        </div>
        {mode === "metric" && (
          <div>
            <label htmlFor="metric-filter" className="block text-xs font-medium text-slate-700">
              Metric
            </label>
            <select id="metric-filter" value={metric} onChange={(e) => setMetric(e.target.value)} className={`${input} mt-1 w-48`}>
              {metrics.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </div>
        )}
        {mode === "tag" && (
          <div>
            <label htmlFor="tag-filter" className="block text-xs font-medium text-slate-700">
              Tag
            </label>
            <select id="tag-filter" value={tag} onChange={(e) => setTag(e.target.value)} className={`${input} mt-1 w-48`}>
              {tags.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
        )}
      </div>
      <DataState {...results} isEmpty={(d) => d.length === 0} empty="No cases match this filter." loadingLabel="Loading cases">
        {(rows) => (
          <div className="relative overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <p className="sr-only" aria-live="polite">
              {rows.length} cases shown
            </p>
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-600">
                <tr>
                  <th scope="col" className="px-3 py-2">Case</th>
                  <th scope="col" className="px-3 py-2">Input</th>
                  <th scope="col" className="px-3 py-2">Result</th>
                  <th scope="col" className="px-3 py-2 text-right">Latency</th>
                  <th scope="col" className="px-3 py-2">Failed metrics</th>
                  <th scope="col" className="px-3 py-2">
                    <span className="sr-only">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 align-top">
                {rows.map((r) => {
                  const isOpen = open === r.id;
                  const failed = r.scores.filter((s) => s.status === "scored" && s.passed === false).map((s) => s.metric);
                  return (
                    <Fragment key={r.id}>
                      <tr className={r.passed === false ? "bg-red-50/40" : undefined}>
                        <td className="px-3 py-2 font-mono text-xs">{r.external_id}</td>
                        <td className="max-w-xs px-3 py-2">
                          <span className="line-clamp-2">{r.input ?? "--"}</span>
                        </td>
                        <td className="px-3 py-2">
                          <PassPill passed={r.passed} />
                          {r.error && (
                            <Badge tone="red" title={r.error}>
                              error
                            </Badge>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">{ms(r.latency_ms)}</td>
                        <td className="px-3 py-2 font-mono text-xs text-red-800">{failed.join(", ") || "--"}</td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            className={btn}
                            aria-expanded={isOpen}
                            aria-controls={`case-${r.id}`}
                            onClick={() => setOpen(isOpen ? null : r.id)}
                          >
                            {isOpen ? "Hide" : "Details"}
                          </button>
                        </td>
                      </tr>
                      {isOpen && (
                        <tr id={`case-${r.id}`}>
                          <td colSpan={6} className="bg-slate-50 px-3 py-3">
                            <CaseDetail row={r} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </DataState>
    </section>
  );
}

function CaseDetail({ row }: { row: CaseResult }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <h3 className="text-xs font-semibold uppercase text-slate-600">Expected</h3>
          <p className="whitespace-pre-wrap">{row.expected_output ?? "--"}</p>
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase text-slate-600">Output</h3>
          <p className="whitespace-pre-wrap">{row.output_text ?? "--"}</p>
        </div>
      </div>
      {row.error && (
        <p role="note" className="rounded border border-red-300 bg-red-50 p-2 text-red-900">
          Error: {row.error}
        </p>
      )}
      <p className="text-xs text-slate-600">
        tokens in/out {row.input_tokens}/{row.output_tokens}
        {row.tokens_estimated ? " (estimated)" : ""} | cost {usd(row.cost_usd)} | attempts {row.attempts}
        {row.tags.length > 0 && <> | tags: {row.tags.join(", ")}</>}
        {row.trace_id && (
          <>
            {" "}
            |{" "}
            <Link to={`/traces/${row.trace_id}`} className={link}>
              View trace
            </Link>
          </>
        )}
      </p>
      <ul className="space-y-1">
        {row.scores.map((s) => (
          <li key={s.metric} className="rounded border border-slate-200 bg-white p-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-xs font-semibold">{s.metric}</span>
              {s.status === "scored" ? <PassPill passed={s.passed} /> : <Badge tone={s.status === "skipped" ? "gray" : "red"}>{s.status}</Badge>}
              {s.is_estimate && <Badge tone="purple">estimate</Badge>}
              {!s.gating && <Badge>non-gating</Badge>}
              <span className="ml-auto text-xs tabular-nums text-slate-700">value {num(s.value, 4)}</span>
            </div>
            {s.explanation && <p className="mt-1 text-xs text-slate-700">{s.explanation}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
