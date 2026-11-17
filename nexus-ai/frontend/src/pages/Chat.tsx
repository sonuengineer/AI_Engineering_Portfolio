import { useState, type FormEvent } from "react";
import { api, post } from "../api/client";
import type { AskResponse, ChatMessage, Citation, Conversation } from "../api/types";
import { useAsync } from "../components/useAsync";
import { Badge, Button, Card, EmptyState, ErrorBanner, ProviderBadge, cx } from "../components/ui";

const EXAMPLES = [
  "What discount can an account manager approve?",
  "Why did Harbor Marine Systems reject batch MC-5521?",
  "When did the Ironclad contract expire?",
  "Which customer had late hydraulic deliveries?",
  "What is the capital of France?",
];

interface Turn { question: string; response?: AskResponse; history?: ChatMessage }

export function Chat() {
  const convs = useAsync(() => api<Conversation[]>("/conversations"));
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [selected, setSelected] = useState<AskResponse | null>(null);

  const ask = async (q: string) => {
    if (!q.trim()) return;
    setBusy(true);
    setError(undefined);
    try {
      const r = await post<AskResponse>("/chat/ask", { question: q, conversation_id: conversationId });
      setConversationId(r.conversation_id);
      setTurns((t) => [...t, { question: q, response: r }]);
      setSelected(r);
      setQuestion("");
      void convs.reload(true);
    } catch (e) { setError(e); } finally { setBusy(false); }
  };

  const openConversation = async (id: string) => {
    setError(undefined);
    try {
      const msgs = await api<ChatMessage[]>(`/conversations/${id}/messages`);
      const rebuilt: Turn[] = [];
      for (const m of msgs) {
        if (m.role === "user") rebuilt.push({ question: m.content });
        else if (rebuilt.length) rebuilt[rebuilt.length - 1]!.history = m;
      }
      setConversationId(id); setTurns(rebuilt); setSelected(null);
    } catch (e) { setError(e); }
  };

  const submit = (e: FormEvent) => { e.preventDefault(); void ask(question); };

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr_360px]">
      <aside aria-label="Conversations" className="space-y-2">
        <Button variant="secondary" className="w-full" onClick={() => { setConversationId(null); setTurns([]); setSelected(null); }}>New conversation</Button>
        <ul className="space-y-1 text-sm">
          {(convs.data ?? []).map((c) => (
            <li key={c.id}>
              <button onClick={() => void openConversation(c.id)} className={cx("w-full truncate rounded px-2 py-1.5 text-left hover:bg-slate-100", c.id === conversationId && "bg-brand-50 text-brand-700")}>{c.title}</button>
            </li>
          ))}
        </ul>
      </aside>

      <section aria-label="Chat" className="space-y-4">
        <h1 className="text-xl font-semibold">Ask your enterprise knowledge</h1>
        {turns.length === 0 && (
          <EmptyState title="Ask a question about indexed documents">
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {EXAMPLES.map((ex) => <button key={ex} onClick={() => void ask(ex)} disabled={busy} className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs hover:bg-slate-50">{ex}</button>)}
            </div>
          </EmptyState>
        )}
        <ol className="space-y-4" aria-live="polite">
          {turns.map((t, i) => {
            const answer = t.response?.answer ?? t.history?.content;
            const cites: Citation[] = t.response?.citations ?? t.history?.citations ?? [];
            const insufficient = t.response?.insufficient_evidence ?? Boolean(t.history?.meta?.insufficient_evidence);
            return (
              <li key={i} className="space-y-2">
                <p className="ml-auto max-w-[85%] rounded-lg bg-brand-600 px-3 py-2 text-sm text-white w-fit">{t.question}</p>
                <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    {insufficient ? <Badge tone="amber">Insufficient evidence</Badge> : <Badge tone="green">Grounded: {cites.length} source{cites.length === 1 ? "" : "s"}</Badge>}
                    {t.response && <ProviderBadge provider={t.response.provider} />}
                    {t.response && <span className="text-xs text-slate-500">{t.response.latency_ms} ms</span>}
                    {t.response && <button onClick={() => setSelected(t.response!)} className="text-xs text-brand-700 underline">Show retrieval</button>}
                  </div>
                  <p className="whitespace-pre-wrap leading-relaxed">{answer}</p>
                  {cites.length > 0 && (
                    <ul className="mt-3 space-y-1 border-t border-slate-100 pt-2">
                      {cites.map((c) => (
                        <li key={c.ref} className="text-xs text-slate-600">
                          <span className="font-semibold">[{c.ref}]</span> {c.document_title}{c.page ? `, page ${c.page}` : ""}
                          {c.flagged && <Badge tone="red" title="This chunk matched prompt-injection patterns; it is treated as untrusted data.">flagged content</Badge>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
        <ErrorBanner error={error} />
        <form onSubmit={submit} className="flex gap-2">
          <label htmlFor="q" className="sr-only">Question</label>
          <input id="q" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={2000} placeholder="Ask about policies, customers, contracts..."
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <Button type="submit" busy={busy} disabled={!question.trim()}>Ask</Button>
        </form>
      </section>

      <aside aria-label="Sources and retrieval" className="space-y-4">
        <Card title="Sources">
          {!selected ? <p className="text-sm text-slate-500">Ask a question to see cited sources.</p> :
            selected.citations.length === 0 ? <p className="text-sm text-slate-500">No sources cited. The assistant abstained instead of guessing.</p> :
            <ul className="space-y-3">
              {selected.citations.map((c) => (
                <li key={c.ref} className="text-xs">
                  <p className="font-semibold text-slate-700">[{c.ref}] {c.document_title}{c.page ? ` -- p.${c.page}` : ""}</p>
                  <blockquote className="mt-1 border-l-2 border-slate-200 pl-2 text-slate-600">{c.snippet}</blockquote>
                </li>
              ))}
            </ul>}
        </Card>
        {selected && (
          <Card title="Hybrid retrieval (vector + keyword, RRF, rerank)">
            <table className="w-full text-xs">
              <thead><tr className="text-left text-slate-500"><th className="py-1">Chunk</th><th>Vec</th><th>Kw</th><th>Score</th></tr></thead>
              <tbody>
                {selected.retrieval.map((r) => (
                  <tr key={r.chunk_id} className="border-t border-slate-100">
                    <td className="py-1 pr-2">{r.document_title.slice(0, 28)}{r.page ? ` p${r.page}` : ""}{r.flagged && " (!)"}</td>
                    <td>{r.vector_rank ?? "-"}</td><td>{r.keyword_rank ?? "-"}</td><td>{r.rerank_score.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">
              Tokens: {selected.usage.input_tokens}+{selected.usage.output_tokens}{selected.usage.tokens_are_estimates ? " (estimated)" : ""} -- cost ${selected.usage.estimated_cost_usd.toFixed(4)}
            </p>
          </Card>
        )}
      </aside>
    </div>
  );
}
