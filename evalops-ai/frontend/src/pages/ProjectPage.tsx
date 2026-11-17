import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Project } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { DataState } from "../components/DataState";
import { PageTitle, btnPrimary, link } from "../components/Layout";
import { useApi } from "../lib/useApi";
import { RunsSection } from "./project/RunsSection";
import { DatasetsSection } from "./project/DatasetsSection";
import { ConfigSection } from "./project/ConfigSection";

const TABS = [
  { id: "runs", label: "Runs" },
  { id: "datasets", label: "Datasets" },
  { id: "config", label: "Targets & evaluators" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find((t) => t.id === params.get("tab"))?.id ?? "runs") as TabId;
  const { canWrite } = useAuth();
  const project = useApi((signal) => api<Project>(`/api/v1/projects/${projectId}`, { signal }), [projectId]);

  return (
    <DataState {...project} loadingLabel="Loading project">
      {(p) => (
        <>
          <p className="mb-1 text-sm">
            <Link to="/" className={link}>
              Projects
            </Link>{" "}
            /
          </p>
          <div className="flex flex-wrap items-start gap-3">
            <div className="mr-auto min-w-0">
              <PageTitle sub={p.description}>{p.name}</PageTitle>
            </div>
            {canWrite && (
              <Link to={`/projects/${p.id}/runs/new`} className={btnPrimary}>
                New run
              </Link>
            )}
          </div>
          <div role="tablist" aria-label="Project sections" className="mb-4 flex flex-wrap gap-1 border-b border-slate-200">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                type="button"
                id={`tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls={`panel-${t.id}`}
                onClick={() => setParams({ tab: t.id }, { replace: true })}
                className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-blue-600 ${
                  tab === t.id ? "border-blue-700 text-blue-800" : "border-transparent text-slate-700 hover:text-slate-900"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === "runs" && <RunsSection projectId={p.id} />}
            {tab === "datasets" && <DatasetsSection projectId={p.id} />}
            {tab === "config" && <ConfigSection projectId={p.id} />}
          </div>
        </>
      )}
    </DataState>
  );
}
