// Minimal safe markdown renderer (headings, bullets, paragraphs). Renders text nodes only --
// never HTML -- so report content derived from untrusted documents cannot inject markup.
import type { ReactNode } from "react";

function inline(text: string): ReactNode {
  const parts = text.split(/(EVIDENCE:|HYPOTHESIS \((?:low|medium|high)\):|RECOMMENDED ACTION:)/);
  return parts.map((p, i) => {
    if (p === "EVIDENCE:") return <strong key={i} className="text-emerald-700">EVIDENCE: </strong>;
    if (p.startsWith("HYPOTHESIS")) return <strong key={i} className="text-violet-700">{p} </strong>;
    if (p === "RECOMMENDED ACTION:") return <strong key={i} className="text-brand-700">RECOMMENDED ACTION: </strong>;
    return <span key={i}>{p}</span>;
  });
}

export function Markdown({ source }: { source: string }) {
  const out: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      out.push(<ul key={`ul${out.length}`} className="my-2 list-disc space-y-1 pl-5">{list.map((l, i) => <li key={i}>{inline(l)}</li>)}</ul>);
      list = [];
    }
  };
  for (const line of source.split("\n")) {
    if (line.startsWith("- ")) { list.push(line.slice(2)); continue; }
    flush();
    if (line.startsWith("# ")) out.push(<h2 key={out.length} className="mt-2 text-lg font-semibold">{line.slice(2)}</h2>);
    else if (line.startsWith("## ")) out.push(<h3 key={out.length} className="mt-4 font-semibold text-slate-800">{line.slice(3)}</h3>);
    else if (line.trim()) out.push(<p key={out.length} className="my-1">{inline(line)}</p>);
  }
  flush();
  return <div className="text-sm leading-relaxed text-slate-700">{out}</div>;
}
