import { useState } from "react";
import { api, ApiError } from "../api";
import { AnswerPanel } from "../components/AnswerPanel";
import { ErrorBox, Loading } from "../components/Feedback";
import type { AskResponse } from "../types";

export const EXAMPLES = [
  "Revenue by month in 2025",
  "Top 5 products by revenue last quarter",
  "Which region had the highest conversion rate in 2025?",
  "On-time delivery rate by supplier this year",
  "Average order value by sales channel in 2025",
  "Who are our best customers?",
  "Compare revenue in 2025 vs 2026",
  "Delete all cancelled orders",
];

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);

  async function run(q: string) {
    const text = q.trim();
    if (!text) return;
    setQuestion(text);
    setAsked(text);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.ask(text));
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "network", "Could not reach the API", null));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <form onSubmit={(e) => { e.preventDefault(); void run(question); }} className="space-y-2">
        <label htmlFor="question" className="block text-sm font-medium text-slate-700">Ask a business question</label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input id="question" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500}
            placeholder="e.g. Revenue by category for the West region last quarter"
            className="focus-ring grow rounded-md border border-slate-300 bg-white px-3 py-2" />
          <button type="submit" disabled={loading || !question.trim()}
            className="focus-ring rounded-md bg-teal-700 px-4 py-2 font-medium text-white hover:bg-teal-800 disabled:opacity-50">
            Ask
          </button>
        </div>
      </form>

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Examples</h2>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" onClick={() => void run(ex)}
              className="focus-ring rounded-full border border-slate-300 bg-white px-3 py-1 text-sm text-slate-700 hover:bg-slate-100">
              {ex}
            </button>
          ))}
        </div>
      </div>

      {loading ? <Loading label="Planning, validating and running the query" /> : null}
      {error ? <ErrorBox message={`${error.message}${error.code ? ` (${error.code})` : ""}`} requestId={error.requestId} /> : null}
      {result ? (
        <AnswerPanel result={result} question={asked} onClarify={(o) => void run(o)}
          onSave={async (name) => { if (result.plan) await api.createReport(name, asked, result.plan); }} />
      ) : null}
    </div>
  );
}
