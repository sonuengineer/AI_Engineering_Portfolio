import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { usePageMeta } from "../components/Seo";
import { useProgress } from "../components/useProgress";
import { HANDBOOK_NAMES, handbook, type HandbookKey } from "../data/interview";
import { DIFFICULTIES, type Difficulty, type Question } from "../data/interviewTypes";
import { NotFound } from "./NotFound";

const DIFF_STYLE: Record<Difficulty, string> = {
  beginner: "bg-emerald-500/15 text-emerald-300", intermediate: "bg-sky-500/15 text-sky-300",
  advanced: "bg-violet-500/15 text-violet-300", senior: "bg-rose-500/15 text-rose-300",
};
const TABS = ["practice", "exercises", "walkthroughs", "mock"] as const;
type Tab = (typeof TABS)[number];

export function QuestionCard({ q, ns, onPrev, onNext, position }: { q: Question; ns: string; onPrev?: () => void; onNext?: () => void; position: string }) {
  const [revealed, setRevealed] = useState(false);
  const { learned, bookmarked, toggle } = useProgress();
  const id = `${ns}:${q.id}`;
  return (
    <article aria-labelledby={`q-${q.id}`} className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`rounded px-2 py-0.5 font-medium ${DIFF_STYLE[q.difficulty]}`}>{q.difficulty}</span>
        {q.kind === "proposed_extension" && <span className="rounded bg-amber-500/15 px-2 py-0.5 text-amber-300">proposed extension (not implemented)</span>}
        <span className="text-slate-500">{position}</span>
      </div>
      <h2 id={`q-${q.id}`} className="text-lg font-semibold text-white">{q.question}</h2>
      {!revealed ? (
        <button onClick={() => setRevealed(true)} className="rounded-md bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400">Reveal answer</button>
      ) : (
        <div className="space-y-4" aria-live="polite">
          <section><h3 className="text-xs font-semibold uppercase text-slate-400">Expected answer</h3><p className="mt-1 whitespace-pre-line text-slate-200">{q.answer}</p></section>
          {q.reasoning && <section><h3 className="text-xs font-semibold uppercase text-slate-400">Why / what the interviewer looks for</h3><p className="mt-1 whitespace-pre-line text-sm text-slate-300">{q.reasoning}</p></section>}
          {q.code_refs.length > 0 && <section><h3 className="text-xs font-semibold uppercase text-slate-400">Code references</h3>
            <ul className="mt-1 space-y-0.5">{q.code_refs.map((r) => <li key={r}><code className="text-xs text-indigo-300">{r}</code></li>)}</ul></section>}
          {q.follow_ups.length > 0 && <section><h3 className="text-xs font-semibold uppercase text-slate-400">Likely follow-ups</h3>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-300">{q.follow_ups.map((f) => <li key={f}>{f}</li>)}</ul></section>}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 border-t border-slate-800 pt-4">
        <button aria-pressed={!!learned[id]} onClick={() => toggle("learned", id)} className={`rounded-md px-3 py-1.5 text-sm ${learned[id] ? "bg-emerald-600 text-white" : "border border-slate-600 text-slate-200 hover:bg-slate-800"}`}>
          {learned[id] ? "Learned" : "Mark learned"}</button>
        <button aria-pressed={!!bookmarked[id]} onClick={() => toggle("bookmarked", id)} className={`rounded-md px-3 py-1.5 text-sm ${bookmarked[id] ? "bg-amber-500 text-slate-900" : "border border-slate-600 text-slate-200 hover:bg-slate-800"}`}>
          {bookmarked[id] ? "Bookmarked" : "Bookmark"}</button>
        <span className="ml-auto flex gap-2">
          <button onClick={onPrev} disabled={!onPrev} className="rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:opacity-40">Previous</button>
          <button onClick={onNext} disabled={!onNext} className="rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-200 disabled:opacity-40">Next</button>
        </span>
      </div>
    </article>
  );
}

export function InterviewProject() {
  const { project } = useParams();
  const hb = handbook(project);
  const name = project && project in HANDBOOK_NAMES ? HANDBOOK_NAMES[project as HandbookKey] : "Handbook";
  usePageMeta(`${name} interview prep`, `${name} interview questions with answers, code references and follow-ups.`);
  const [params, setParams] = useSearchParams();
  const tab = (TABS.includes(params.get("tab") as Tab) ? params.get("tab") : "practice") as Tab;
  const topic = params.get("topic") ?? "all";
  const difficulty = params.get("difficulty") ?? "all";
  const onlyBookmarked = params.get("bookmarked") === "1";
  const { learned, bookmarked } = useProgress();
  const [index, setIndex] = useState(0);
  const set = (k: string, v: string | null) => { const n = new URLSearchParams(params); if (v === null) n.delete(k); else n.set(k, v); setParams(n, { replace: true }); setIndex(0); };

  const filtered = useMemo(() => (hb?.questions ?? []).filter((q) =>
    (topic === "all" || q.topic === topic) && (difficulty === "all" || q.difficulty === difficulty) &&
    (!onlyBookmarked || bookmarked[`${project}:${q.id}`])), [hb, topic, difficulty, onlyBookmarked, bookmarked, project]);

  if (!project || !(project in HANDBOOK_NAMES)) return <NotFound />;
  if (!hb) return <div className="space-y-3"><h1 className="text-2xl font-bold text-white">{name}</h1><p className="text-amber-300">This handbook has not been generated yet.</p></div>;
  const current = filtered[Math.min(index, Math.max(0, filtered.length - 1))];
  const ns = project;
  const learnedCount = hb.questions.filter((q) => learned[`${ns}:${q.id}`]).length;
  const byId = new Map(hb.questions.map((q) => [q.id, q]));

  return (
    <div className="space-y-6">
      <nav aria-label="Breadcrumb" className="text-sm text-slate-400"><Link to="/interview" className="hover:text-white">Interview prep</Link> / {name}</nav>
      <header className="space-y-2">
        <h1 className="text-3xl font-bold text-white">{hb.title}</h1>
        <p className="text-sm text-slate-400">{hb.questions.length} questions / {learnedCount} learned / source: {hb.generated_from}</p>
      </header>
      <div role="tablist" aria-label="Sections" className="flex flex-wrap gap-1">
        {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => set("tab", t)}
          className={`rounded-md px-3 py-1.5 text-sm capitalize ${tab === t ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"}`}>{t === "mock" ? "mock interviews" : t}</button>)}
      </div>

      {tab === "practice" && (
        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          <aside className="space-y-4" aria-label="Filters">
            <div>
              <label htmlFor="topic" className="text-xs font-semibold uppercase text-slate-400">1. Topic</label>
              <select id="topic" value={topic} onChange={(e) => set("topic", e.target.value)} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-2 text-sm text-white">
                <option value="all">All topics ({hb.questions.length})</option>
                {hb.topics.map((t) => <option key={t.id} value={t.id}>{t.title} ({hb.questions.filter((q) => q.topic === t.id).length})</option>)}
              </select>
            </div>
            <fieldset>
              <legend className="text-xs font-semibold uppercase text-slate-400">2. Difficulty</legend>
              <div className="mt-1 flex flex-wrap gap-1">
                {["all", ...DIFFICULTIES].map((d) => <button key={d} aria-pressed={difficulty === d} onClick={() => set("difficulty", d)}
                  className={`rounded px-2 py-1 text-xs capitalize ${difficulty === d ? "bg-indigo-500 text-white" : "bg-slate-800 text-slate-300"}`}>{d}</button>)}
              </div>
            </fieldset>
            <label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={onlyBookmarked} onChange={(e) => set("bookmarked", e.target.checked ? "1" : null)} /> Bookmarked only</label>
            <ol className="max-h-96 space-y-0.5 overflow-auto text-xs" aria-label="Questions">
              {filtered.map((q, i) => (
                <li key={q.id}><button onClick={() => setIndex(i)} className={`w-full truncate rounded px-2 py-1 text-left ${current?.id === q.id ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"}`}>
                  {learned[`${ns}:${q.id}`] ? "[x] " : ""}{q.question}</button></li>))}
            </ol>
          </aside>
          <div>
            {current ? <QuestionCard key={current.id} q={current} ns={ns} position={`3. Question ${filtered.indexOf(current) + 1} of ${filtered.length}`}
              onPrev={index > 0 ? () => setIndex(index - 1) : undefined} onNext={index < filtered.length - 1 ? () => setIndex(index + 1) : undefined} />
              : <p className="text-slate-400">No questions match these filters.</p>}
          </div>
        </div>
      )}

      {tab === "exercises" && (
        <div className="space-y-4">{hb.exercises.map((ex) => (
          <details key={ex.id} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <summary className="cursor-pointer font-semibold text-white">{ex.title} <span className={`ml-2 rounded px-2 py-0.5 text-xs ${DIFF_STYLE[ex.difficulty]}`}>{ex.difficulty}</span></summary>
            <p className="mt-3 whitespace-pre-line text-sm text-slate-300">{ex.prompt}</p>
            <h3 className="mt-3 text-xs font-semibold uppercase text-slate-400">Solution outline</h3>
            <p className="whitespace-pre-line text-sm text-slate-300">{ex.solution_outline}</p>
            <h3 className="mt-3 text-xs font-semibold uppercase text-slate-400">Evaluation criteria</h3>
            <ul className="list-disc pl-5 text-sm text-slate-300">{ex.evaluation_criteria.map((c) => <li key={c}>{c}</li>)}</ul>
          </details>))}</div>
      )}

      {tab === "walkthroughs" && (
        <div className="space-y-4">{hb.walkthroughs.map((w) => (
          <section key={w.title} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <h2 className="font-semibold text-white">{w.title}</h2>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-300">{w.steps.map((s) => <li key={s}>{s}</li>)}</ol>
          </section>))}</div>
      )}

      {tab === "mock" && (
        <div className="space-y-4">{hb.mock_interviews.map((m) => (
          <section key={m.title} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <h2 className="font-semibold text-white">{m.title} <span className={`ml-2 rounded px-2 py-0.5 text-xs ${DIFF_STYLE[m.level]}`}>{m.level}</span></h2>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-300">
              {m.question_ids.map((id) => <li key={id}>{byId.get(id)?.question ?? `(missing question ${id})`}</li>)}
            </ol>
          </section>))}</div>
      )}
    </div>
  );
}
