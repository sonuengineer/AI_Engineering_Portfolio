export function ProviderBadge({ provider, model }: { provider: string; model?: string | null }) {
  if (provider === "local") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800"
        title="Rule-based planner. No LLM is called; answers are deterministic."
      >
        Deterministic local adapter
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full border border-indigo-300 bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-800">
      LLM planner: {provider}
      {model ? ` (${model})` : ""}
    </span>
  );
}
