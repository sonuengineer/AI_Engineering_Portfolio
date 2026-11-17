import type { LinkValue } from "../config";

/** Renders a real link only when configured; otherwise an honest "not configured" label. */
export function ExternalLink({ link, className = "" }: { link: LinkValue; className?: string }) {
  if (!link.url) {
    return (
      <span className={`inline-flex cursor-not-allowed items-center rounded-md border border-dashed border-slate-600 px-3 py-1.5 text-sm text-slate-400 ${className}`}
        title="Placeholder -- set the corresponding VITE_* variable to publish this link">
        {link.label}: not configured
      </span>
    );
  }
  return (
    <a href={link.url} target="_blank" rel="noopener noreferrer"
      className={`inline-flex items-center rounded-md bg-indigo-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-400 ${className}`}>
      {link.label}<span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}
