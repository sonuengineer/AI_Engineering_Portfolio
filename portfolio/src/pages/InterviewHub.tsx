import { Link } from "react-router-dom";
import { usePageMeta } from "../components/Seo";
import { useProgress } from "../components/useProgress";
import { HANDBOOK_KEYS, HANDBOOK_NAMES, handbook } from "../data/interview";

export function InterviewHub() {
  usePageMeta("Interview preparation", "Project-linked interview question banks with answers, code references, follow-ups, exercises and mock interviews.");
  const { learned, bookmarked, reset } = useProgress();
  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <h1 className="text-3xl font-bold text-white">Interview preparation</h1>
        <p className="max-w-3xl text-slate-300">
          Each question bank was written after inspecting the actual source code. Questions reference real files, and anything
          not implemented is labeled <em>proposed extension</em>. Flow: choose project, topic, difficulty, then reveal the answer and follow-ups.
        </p>
        <p className="text-xs text-slate-500">Progress is stored only in this browser (localStorage). No account is required.</p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        {HANDBOOK_KEYS.map((k) => {
          const hb = handbook(k);
          const ids = hb?.questions.map((q) => `${k}:${q.id}`) ?? [];
          const done = ids.filter((i) => learned[i]).length;
          const marks = ids.filter((i) => bookmarked[i]).length;
          return (
            <Link key={k} to={`/interview/${k}`} className="group rounded-2xl border border-slate-800 bg-slate-900 p-5 hover:border-indigo-500">
              <h2 className="text-lg font-semibold text-white group-hover:text-indigo-300">{HANDBOOK_NAMES[k]}</h2>
              {hb ? (
                <>
                  <p className="mt-1 text-sm text-slate-400">{hb.questions.length} questions / {hb.topics.length} topics / {hb.exercises.length} exercises / {hb.mock_interviews.length} mock interviews</p>
                  <div className="mt-3 h-2 overflow-hidden rounded bg-slate-800" role="progressbar" aria-valuemin={0} aria-valuemax={ids.length} aria-valuenow={done} aria-label={`${HANDBOOK_NAMES[k]} progress`}>
                    <div className="h-full bg-emerald-500" style={{ width: `${ids.length ? (done / ids.length) * 100 : 0}%` }} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{done} learned / {marks} bookmarked</p>
                </>
              ) : <p className="mt-1 text-sm text-amber-300">Handbook not generated yet.</p>}
            </Link>
          );
        })}
      </div>
      <button onClick={() => { if (confirm("Reset all interview progress stored in this browser?")) reset(); }} className="text-xs text-slate-500 underline hover:text-slate-300">Reset progress</button>
    </div>
  );
}
