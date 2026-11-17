import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { Run } from "../../api/types";
import { Badge, StatusPill } from "../../components/Badge";
import { DataState } from "../../components/DataState";
import { btn, link } from "../../components/Layout";
import { dateTime, pct } from "../../lib/format";
import { useApi } from "../../lib/useApi";

export function RunsSection({ projectId }: { projectId: string }) {
  const navigate = useNavigate();
  const runs = useApi((signal) => api<Run[]>("/api/v1/runs", { query: { project_id: projectId }, signal }), [projectId]);
  const [selected, setSelected] = useState<string[]>([]);

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2)));
  }

  function compare(all: Run[]) {
    // Older run is the baseline, newer the candidate.
    const picked = all.filter((r) => selected.includes(r.id));
    picked.sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""));
    if (picked.length === 2) navigate(`/compare?baseline=${picked[0].id}&candidate=${picked[1].id}`);
  }

  return (
    <DataState {...runs} isEmpty={(d) => d.length === 0} empty="No runs yet. Start one with New run." loadingLabel="Loading runs">
      {(all) => (
        <section aria-label="Runs">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <p className="text-sm text-slate-600" aria-live="polite">
              {selected.length}/2 runs selected for comparison (older = baseline)
            </p>
            <button type="button" className={btn} disabled={selected.length !== 2} onClick={() => compare(all)}>
              Compare selected
            </button>
            <button type="button" className={btn} onClick={runs.reload}>
              Refresh
            </button>
          </div>
          <div className="relative overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-600">
                <tr>
                  <th scope="col" className="w-10 px-3 py-2">
                    <span className="sr-only">Select</span>
                  </th>
                  <th scope="col" className="px-3 py-2">Label</th>
                  <th scope="col" className="px-3 py-2">Target</th>
                  <th scope="col" className="px-3 py-2">Provider</th>
                  <th scope="col" className="px-3 py-2">Status</th>
                  <th scope="col" className="px-3 py-2 text-right">Pass rate</th>
                  <th scope="col" className="px-3 py-2">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {all.map((r) => (
                  <tr key={r.id} className={selected.includes(r.id) ? "bg-blue-50" : undefined}>
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.includes(r.id)}
                        onChange={() => toggle(r.id)}
                        aria-label={`Select run ${r.label || r.id} for comparison`}
                        className="h-4 w-4"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <Link to={`/runs/${r.id}`} className={link}>
                        {r.label || r.id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{r.target_name ?? "--"}</td>
                    <td className="px-3 py-2">
                      <span className="mr-1 font-mono text-xs">{r.provider ?? "--"}</span>
                      {r.is_deterministic_provider && <Badge tone="amber">not an LLM</Badge>}
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill status={r.status} />
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{pct(r.summary?.overall_pass_rate)}</td>
                    <td className="px-3 py-2 text-xs text-slate-600">{dateTime(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </DataState>
  );
}
