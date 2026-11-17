import { Link } from "react-router-dom";
import { ExternalLink } from "../components/ExternalLink";
import { usePageMeta } from "../components/Seo";
import { site } from "../config";
import { PROJECTS } from "../data/projects";
import { screenshotsFor } from "../data/artifacts";

const SKILLS = [
  { area: "LLM systems", items: ["Structured outputs", "Provider abstraction", "Token budgets + cost tracking", "Prompt-injection defense"] },
  { area: "Retrieval", items: ["pgvector HNSW", "Full-text + RRF fusion", "Reranking", "Citation validation"] },
  { area: "Agents", items: ["LangGraph supervisors", "Checkpoint + resume", "Typed tool registry", "MCP", "Human-in-the-loop"] },
  { area: "Data + safety", items: ["Semantic layers", "SQL AST validation", "Read-only roles", "Tenant isolation"] },
  { area: "Evaluation", items: ["Deterministic metrics", "LLM-as-judge (labeled)", "Regression gates", "Tracing + redaction"] },
  { area: "Engineering", items: ["FastAPI", "SQLAlchemy 2 + Alembic", "React + TypeScript", "Docker", "GitHub Actions", "Playwright"] },
];

export function Home() {
  usePageMeta("Home", "AI Engineer portfolio: enterprise RAG and agents, safe text-to-SQL, and LLM evaluation systems with verified tests.");
  return (
    <div className="space-y-20">
      <section aria-labelledby="hero" className="space-y-6 pt-6">
        <p className="text-sm font-medium uppercase tracking-widest text-indigo-400">AI Engineer</p>
        <h1 id="hero" className="max-w-4xl text-4xl font-bold leading-tight tracking-tight text-white sm:text-5xl">
          I build LLM systems that cite their sources, ask before acting, and prove their quality.
        </h1>
        <p className="max-w-3xl text-lg text-slate-300">
          Three end-to-end products: an enterprise intelligence platform with agents and human approval, a natural-language BI tool
          that never runs model-written SQL, and an evaluation platform that fails CI when quality regresses.
          Each one ships with tests, Docker, CI, threat models and an interview handbook tied to the actual code.
        </p>
        {site.ownerNameIsPlaceholder && (
          <p className="max-w-3xl rounded-md border border-dashed border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-200">
            Owner name and contact links are placeholders. Configure them with the VITE_* variables in <code>portfolio/.env.example</code>.
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          <Link to="#projects" onClick={(e) => { e.preventDefault(); document.getElementById("projects")?.scrollIntoView(); }} className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-200">See the projects</Link>
          <Link to="/interview" className="rounded-md border border-slate-600 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-900">Interview prep</Link>
          <ExternalLink link={site.github} />
          <ExternalLink link={site.linkedin} />
          <ExternalLink link={site.email.url ? { ...site.email, url: `mailto:${site.email.url}` } : site.email} />
        </div>
      </section>

      <section id="projects" aria-labelledby="projects-title" className="scroll-mt-24 space-y-6">
        <h2 id="projects-title" className="text-2xl font-semibold text-white">Projects</h2>
        <div className="grid gap-6 lg:grid-cols-3">
          {PROJECTS.map((p) => {
            const shot = screenshotsFor(p.slug)[0];
            return (
              <article key={p.slug} className="flex flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
                <div className={`h-1.5 bg-gradient-to-r ${p.accent}`} />
                {shot ? <img src={shot} alt={`${p.name} application screenshot`} loading="lazy" className="h-44 w-full object-cover object-top" /> :
                  <div className="flex h-44 items-center justify-center bg-slate-800/60 px-6 text-center text-xs text-slate-400">No screenshot artifact yet</div>}
                <div className="flex flex-1 flex-col gap-3 p-5">
                  <h3 className="text-lg font-semibold text-white">{p.name}</h3>
                  <p className="text-sm text-slate-300">{p.tagline}</p>
                  <ul className="flex flex-wrap gap-1.5" aria-label="Technologies">
                    {p.tech.slice(0, 6).map((t) => <li key={t} className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">{t}</li>)}
                  </ul>
                  <ul className="space-y-1 text-sm text-slate-400">
                    {p.capabilities.slice(0, 3).map((c) => <li key={c.title}>- {c.title}</li>)}
                  </ul>
                  <div className="mt-auto flex gap-3 pt-2">
                    <Link to={`/projects/${p.slug}`} className="text-sm font-semibold text-indigo-300 hover:text-indigo-200">Details and architecture</Link>
                    <Link to={`/interview/${p.slug}`} className="text-sm text-slate-400 hover:text-white">Interview Q&amp;A</Link>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="skills-title" className="space-y-6">
        <h2 id="skills-title" className="text-2xl font-semibold text-white">What these projects demonstrate</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SKILLS.map((s) => (
            <div key={s.area} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <h3 className="font-semibold text-white">{s.area}</h3>
              <p className="mt-1 text-sm text-slate-400">{s.items.join(" / ")}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
