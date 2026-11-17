import { useState } from "react";

export function SqlBlock({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div className="relative">
      <button
        type="button"
        onClick={copy}
        className="focus-ring absolute right-2 top-2 rounded border border-slate-600 bg-slate-800 px-2 py-0.5 text-xs text-slate-100 hover:bg-slate-700"
        aria-label="Copy SQL to clipboard"
      >
        {copied ? "Copied" : "Copy"}
      </button>
      <pre className="overflow-x-auto rounded-md bg-slate-900 p-3 pr-16 text-xs leading-relaxed text-slate-100">
        <code>{sql}</code>
      </pre>
    </div>
  );
}
