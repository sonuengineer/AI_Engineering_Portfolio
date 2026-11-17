import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Project } from "../api/types";
import { DataState } from "../components/DataState";
import { PageTitle } from "../components/Layout";
import { useApi } from "../lib/useApi";

export function ProjectsPage() {
  const state = useApi((signal) => api<Project[]>("/api/v1/projects", { signal }), []);
  return (
    <>
      <PageTitle>Projects</PageTitle>
      <DataState {...state} isEmpty={(d) => d.length === 0} empty="No projects yet." loadingLabel="Loading projects">
        {(projects) => (
          <ul className="grid gap-3 sm:grid-cols-2">
            {projects.map((p) => (
              <li key={p.id}>
                <Link
                  to={`/projects/${p.id}`}
                  className="block h-full rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-blue-400 focus-visible:outline-2 focus-visible:outline-blue-600"
                >
                  <h2 className="font-semibold text-slate-900">{p.name}</h2>
                  <p className="mt-1 text-sm text-slate-600">{p.description || "No description"}</p>
                  <p className="mt-2 font-mono text-xs text-slate-500">{p.slug}</p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </DataState>
    </>
  );
}
