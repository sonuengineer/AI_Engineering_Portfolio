import { Link, useParams } from "react-router-dom";
import { ArchitecturePreview } from "../components/ArchitecturePreview";
import { ExternalLink } from "../components/ExternalLink";
import { usePageMeta } from "../components/Seo";
import { docUrl, projectLinks } from "../config";
import { artifactsFor, numericLeaves, screenshotsFor, stringField } from "../data/artifacts";
import { projectBySlug } from "../data/projects";
import { NotFound } from "./NotFound";

export function ProjectDetail() {
  const { slug } = useParams();
  const p = projectBySlug(slug);
  usePageMeta(p?.name ?? "Not found", p?.summary ?? "Project not found");
  if (!p) return <NotFound />;
  const links = projectLinks[p.slug]!;
  const shots = screenshotsFor(p.slug);
  const artifacts = Object.entries(artifactsFor(p.slug));

  return (
    <article className="space-y-12">
      <header className="space-y-4">
        <div className={`h-1.5 w-24 rounded bg-gradient-to-r ${p.accent}`} />
        <h1 className="text-4xl font-bold text-white">{p.name}</h1>
        <p className="max-w-3xl text-xl text-slate-300">{p.tagline}</p>
        <p className="max-w-3xl text-slate-400">{p.summary}</p>
        <div className="flex flex-wrap gap-3">
          <ExternalLink link={links.demo} />
          <ExternalLink link={links.repo} />
          <Link to={`/interview/${p.slug}`} className="rounded-md border border-slate-600 px-3 py-1.5 text-sm text-white hover:bg-slate-900">Interview handbook</Link>
        </div>
      </header>

      <section aria-labelledby="problem" className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 id="problem" className="text-xl font-semibold text-white">The problem</h2>
          <p className="text-slate-300">{p.problem}</p>
          <h3 className="pt-2 font-semibold text-white">End-to-end demo flow</h3>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-300">{p.demoFlow.map((s) => <li key={s}>{s}</li>)}</ol>
        </div>
        <div className="space-y-3">
          <h2 className="text-xl font-semibold text-white">Architecture</h2>
          <ArchitecturePreview layers={p.layers} name={p.name} />
        </div>
      </section>

      <section aria-labelledby="caps" className="space-y-4">
        <h2 id="caps" className="text-xl font-semibold text-white">Capabilities</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {p.capabilities.map((c) => (
            <div key={c.title} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
              <h3 className="font-semibold text-white">{c.title}</h3>
              <p className="mt-1 text-sm text-slate-400">{c.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="shots" className="space-y-4">
        <h2 id="shots" className="text-xl font-semibold text-white">Application views</h2>
        {shots.length === 0 ? <p className="text-sm text-slate-400">No screenshots have been captured for this project yet.</p> :
          <div className="grid gap-4 md:grid-cols-2">
            {shots.map((s) => (
              <figure key={s} className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
                <a href={s} target="_blank" rel="noopener noreferrer"><img src={s} alt={`${p.name} -- ${s.split("/").pop()?.replace(/[-_]/g, " ").replace(/\.\w+$/, "")}`} loading="lazy" className="max-h-80 w-full object-cover object-top" /></a>
                <figcaption className="px-3 py-2 text-xs text-slate-400">Captured from the running app by the Playwright e2e suite: {s.split("/").pop()}</figcaption>
              </figure>
            ))}
          </div>}
      </section>

      <section aria-labelledby="metrics" className="space-y-4">
        <h2 id="metrics" className="text-xl font-semibold text-white">Measured results</h2>
        {artifacts.length === 0 ? <p className="text-sm text-slate-400">No benchmark artifacts committed yet, so no numbers are shown.</p> :
          artifacts.map(([file, json]) => (
            <div key={file} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs text-slate-500">Source: <code>{p.slug}/docs/benchmarks/{file}</code>{(stringField(json, "measured_at") ?? stringField(json, "exported_at")) && ` -- recorded ${stringField(json, "measured_at") ?? stringField(json, "exported_at")}`}</p>
              <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {numericLeaves(json).filter((m) => !/(^|\.)(max|mean|scored|run_id)$/.test(m.key) && !m.key.includes("metrics_scored")).slice(0, 32).map((m) => (
                  <div key={m.key} className="rounded-md bg-slate-800/60 p-2">
                    <dt className="text-xs text-slate-400">{m.key}</dt>
                    <dd className="text-lg font-semibold text-white">{m.value.toLocaleString(undefined, { maximumFractionDigits: 3 })}</dd>
                  </div>
                ))}
              </dl>
              {stringField(json, "note") && <p className="mt-2 text-xs text-slate-400">{stringField(json, "note")}</p>}
            </div>
          ))}
      </section>

      <section aria-labelledby="decisions" className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 id="decisions" className="text-xl font-semibold text-white">Key design decisions</h2>
          <ul className="space-y-3">{p.designDecisions.map((d) => <li key={d.title}><p className="font-medium text-white">{d.title}</p><p className="text-sm text-slate-400">{d.why}</p></li>)}</ul>
        </div>
        <div className="space-y-3">
          <h2 className="text-xl font-semibold text-white">Verification and honest limits</h2>
          {p.verification.length > 0 ? <ul className="space-y-1 text-sm text-emerald-300">{p.verification.map((v) => <li key={v}>[verified] {v}</li>)}</ul> :
            <p className="text-sm text-slate-400">Verification summary pending.</p>}
          {p.limitations.length > 0 && <ul className="space-y-1 pt-2 text-sm text-amber-200">{p.limitations.map((v) => <li key={v}>[limit] {v}</li>)}</ul>}
        </div>
      </section>

      <section aria-labelledby="docs" className="space-y-3">
        <h2 id="docs" className="text-xl font-semibold text-white">Documentation</h2>
        <ul className="grid gap-2 sm:grid-cols-2">
          {p.docs.map((d) => {
            const url = docUrl(p.slug, d.path);
            return (
              <li key={d.path} className="rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm">
                {url ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-indigo-300 hover:text-indigo-200">{d.label}</a> : <span className="text-slate-200">{d.label}</span>}
                <span className="block text-xs text-slate-500">{p.slug}/{d.path}</span>
              </li>
            );
          })}
        </ul>
        <div className="flex flex-wrap gap-2 pt-1 text-xs text-slate-500">
          <span>Tech:</span>{p.tech.map((t) => <span key={t} className="rounded bg-slate-800 px-2 py-0.5 text-slate-300">{t}</span>)}
        </div>
      </section>
    </article>
  );
}
