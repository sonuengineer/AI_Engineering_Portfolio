import type { Layer } from "../data/projects";

export function ArchitecturePreview({ layers, name }: { layers: Layer[]; name: string }) {
  return (
    <figure aria-label={`${name} architecture layers`} className="space-y-2">
      {layers.map((l, i) => (
        <div key={l.name} className="grid grid-cols-[110px_1fr] items-stretch gap-2">
          <div className="flex items-center rounded-md bg-slate-800 px-3 text-xs font-semibold uppercase tracking-wide text-slate-300">{l.name}</div>
          <div className="flex flex-wrap gap-2 rounded-md border border-slate-800 bg-slate-900 p-2">
            {l.items.map((it) => <span key={it} className="rounded bg-slate-800/80 px-2 py-1 text-xs text-slate-200">{it}</span>)}
          </div>
          {i < layers.length - 1 && <div aria-hidden className="col-span-2 -my-1 text-center text-xs text-slate-600">|</div>}
        </div>
      ))}
      <figcaption className="text-xs text-slate-500">Simplified layer view. Full Mermaid system, ER and sequence diagrams are in docs/architecture.md.</figcaption>
    </figure>
  );
}
