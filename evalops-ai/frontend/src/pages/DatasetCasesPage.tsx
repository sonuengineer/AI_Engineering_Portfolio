import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { TestCase } from "../api/types";
import { Badge } from "../components/Badge";
import { DataState } from "../components/DataState";
import { PageTitle, btn, input, link } from "../components/Layout";
import { useApi } from "../lib/useApi";

const PAGE_SIZE = 20;

export function DatasetCasesPage() {
  const { projectId = "", versionId = "" } = useParams();
  const [page, setPage] = useState(0);
  const [tagDraft, setTagDraft] = useState("");
  const [tag, setTag] = useState("");
  // Ask for one extra row so we know whether a next page exists (the API returns no total).
  const cases = useApi(
    (signal) =>
      api<TestCase[]>(`/api/v1/dataset-versions/${versionId}/cases`, {
        query: { limit: PAGE_SIZE + 1, offset: page * PAGE_SIZE, tag: tag || undefined },
        signal,
      }),
    [versionId, page, tag],
  );

  return (
    <>
      <p className="mb-1 text-sm">
        <Link to={`/projects/${projectId}?tab=datasets`} className={link}>
          Back to datasets
        </Link>
      </p>
      <PageTitle sub={<span className="font-mono text-xs">version {versionId}</span>}>Dataset cases</PageTitle>
      <form
        className="mb-3 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(0);
          setTag(tagDraft.trim());
        }}
      >
        <div>
          <label htmlFor="tag-filter" className="block text-xs font-medium text-slate-700">
            Filter by tag
          </label>
          <input id="tag-filter" value={tagDraft} onChange={(e) => setTagDraft(e.target.value)} className={`${input} mt-1 w-48`} />
        </div>
        <button type="submit" className={btn}>
          Apply
        </button>
      </form>
      <DataState {...cases} isEmpty={(d) => d.length === 0} empty="No cases match." loadingLabel="Loading cases">
        {(rows) => (
          <>
            <div className="relative overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-600">
                  <tr>
                    <th scope="col" className="px-3 py-2">ID</th>
                    <th scope="col" className="px-3 py-2">Input</th>
                    <th scope="col" className="px-3 py-2">Expected</th>
                    <th scope="col" className="px-3 py-2">Tags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 align-top">
                  {rows.slice(0, PAGE_SIZE).map((c) => (
                    <tr key={c.id}>
                      <td className="px-3 py-2 font-mono text-xs">{c.external_id}</td>
                      <td className="px-3 py-2">{c.input}</td>
                      <td className="px-3 py-2 text-slate-700">{c.expected_output ?? "--"}</td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          {c.tags.map((t) => (
                            <Badge key={t}>{t}</Badge>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <nav aria-label="Pagination" className="mt-3 flex items-center gap-2">
              <button type="button" className={btn} disabled={page === 0 || cases.loading} onClick={() => setPage((p) => p - 1)}>
                Previous
              </button>
              <span className="text-sm text-slate-700">Page {page + 1}</span>
              <button
                type="button"
                className={btn}
                disabled={rows.length <= PAGE_SIZE || cases.loading}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </nav>
          </>
        )}
      </DataState>
    </>
  );
}
