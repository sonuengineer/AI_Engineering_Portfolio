import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { Dataset, DatasetVersion } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { DataState, ErrorBox } from "../../components/DataState";
import { btn, input, link } from "../../components/Layout";
import { dateTime, shortHash } from "../../lib/format";
import { useApi } from "../../lib/useApi";

export function DatasetsSection({ projectId }: { projectId: string }) {
  const { canWrite } = useAuth();
  const datasets = useApi((signal) => api<Dataset[]>(`/api/v1/projects/${projectId}/datasets`, { signal }), [projectId]);
  return (
    <DataState {...datasets} isEmpty={(d) => d.length === 0} empty="No datasets in this project." loadingLabel="Loading datasets">
      {(ds) => (
        <div className="space-y-4">
          {ds.map((d) => (
            <section key={d.id} aria-label={`Dataset ${d.name}`} className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="font-mono text-base font-semibold">{d.name}</h2>
              <p className="text-sm text-slate-600">{d.description}</p>
              <div className="relative mt-3 overflow-x-auto">
                <table className="w-full min-w-[560px] text-left text-sm">
                  <thead className="text-xs uppercase text-slate-600">
                    <tr>
                      <th scope="col" className="py-1 pr-3">Version</th>
                      <th scope="col" className="py-1 pr-3">Hash</th>
                      <th scope="col" className="py-1 pr-3 text-right">Cases</th>
                      <th scope="col" className="py-1 pr-3">Source / notes</th>
                      <th scope="col" className="py-1">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {[...d.versions].sort((a, b) => b.version - a.version).map((v) => (
                      <tr key={v.id}>
                        <td className="py-1.5 pr-3">
                          <Link to={`/projects/${projectId}/dataset-versions/${v.id}`} className={link}>
                            v{v.version} cases
                          </Link>
                        </td>
                        <td className="py-1.5 pr-3 font-mono text-xs" title={v.content_hash}>
                          {shortHash(v.content_hash, 12)}
                        </td>
                        <td className="py-1.5 pr-3 text-right tabular-nums">{v.case_count}</td>
                        <td className="py-1.5 pr-3 text-xs text-slate-600">
                          {v.source_filename ?? "--"}
                          {v.notes ? ` -- ${v.notes}` : ""}
                        </td>
                        <td className="py-1.5 text-xs text-slate-600">{dateTime(v.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {canWrite && <UploadVersionForm datasetId={d.id} onUploaded={datasets.reload} />}
            </section>
          ))}
        </div>
      )}
    </DataState>
  );
}

function UploadVersionForm({ datasetId, onUploaded }: { datasetId: string; onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<DatasetVersion | null>(null);
  const fileId = `file-${datasetId}`;
  const notesId = `notes-${datasetId}`;

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!file) return;
    const form = e.currentTarget;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("notes", notes);
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const v = await api<DatasetVersion>(`/api/v1/datasets/${datasetId}/versions`, { method: "POST", body: fd });
      setDone(v);
      setFile(null);
      setNotes("");
      form.reset();
      onUploaded();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="mt-3 rounded border border-slate-200 p-2">
      <summary className="cursor-pointer text-sm font-medium text-slate-800">Upload new version (.jsonl)</summary>
      <form onSubmit={onSubmit} className="mt-2 grid gap-2 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <div>
          <label htmlFor={fileId} className="block text-xs font-medium text-slate-700">
            JSONL file
          </label>
          <input
            id={fileId}
            type="file"
            accept=".jsonl,.ndjson"
            required
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm"
          />
        </div>
        <div>
          <label htmlFor={notesId} className="block text-xs font-medium text-slate-700">
            Notes
          </label>
          <input id={notesId} value={notes} onChange={(e) => setNotes(e.target.value)} className={`${input} mt-1`} />
        </div>
        <button type="submit" className={btn} disabled={busy || !file}>
          {busy ? "Uploading..." : "Upload"}
        </button>
      </form>
      <div aria-live="polite">
        {done && (
          <p className="mt-2 text-sm text-green-800">
            Created v{done.version} with {done.case_count} cases (hash {shortHash(done.content_hash, 12)}).
          </p>
        )}
      </div>
      {error !== null && <ErrorBox error={error} />}
    </details>
  );
}
