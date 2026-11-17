import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { ErrorBox, Loading } from "../components/Feedback";
import type { Catalog } from "../types";

export function CatalogPage() {
  const [cat, setCat] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.catalog().then(setCat).catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Failed to load catalog"));
  }, []);
  if (error) return <ErrorBox message={error} />;
  if (!cat) return <Loading label="Loading catalog" />;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Data catalog</h1>
        <p className="text-sm text-slate-500">Data range {cat.data_range.start} to {cat.data_range.end}. Only these tables and columns can ever be queried.</p>
      </div>
      <section aria-labelledby="metrics-h">
        <h2 id="metrics-h" className="mb-2 font-semibold">Metrics</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {cat.metrics.map((m) => (
            <div key={m.name} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
              <p className="font-medium">{m.label} <code className="text-xs text-slate-500">{m.name}</code></p>
              <p className="text-slate-600">{m.description}</p>
              <p className="mt-1 text-xs text-slate-400">Also: {m.synonyms.slice(0, 5).join(", ")}</p>
            </div>
          ))}
        </div>
      </section>
      <section aria-labelledby="dims-h">
        <h2 id="dims-h" className="mb-2 font-semibold">Dimensions</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full rounded-md border border-slate-200 bg-white text-sm">
            <thead className="bg-slate-100"><tr><th scope="col" className="px-3 py-2 text-left">Name</th><th scope="col" className="px-3 py-2 text-left">Description</th><th scope="col" className="px-3 py-2 text-left">Available for</th></tr></thead>
            <tbody>
              {cat.dimensions.map((d) => (
                <tr key={d.name} className="border-t border-slate-100">
                  <td className="px-3 py-1.5 font-medium">{d.label}</td><td className="px-3 py-1.5 text-slate-600">{d.description}</td><td className="px-3 py-1.5 text-slate-500">{d.facts.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section aria-labelledby="tables-h">
        <h2 id="tables-h" className="mb-2 font-semibold">Tables (from information_schema)</h2>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {cat.tables.map((t) => (
            <div key={t.name} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
              <p className="font-mono font-medium">{t.name}</p>
              <p className="text-xs text-slate-500">{t.description}</p>
              <ul className="mt-1 text-xs">
                {t.columns.map((c) => <li key={c.name}><span className="font-mono">{c.name}</span> <span className="text-slate-400">{c.type}</span></li>)}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
