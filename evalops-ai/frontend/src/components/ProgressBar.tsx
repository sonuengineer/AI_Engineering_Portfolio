export function ProgressBar({ done, total, status }: { done: number; total: number; status: string }) {
  const ratio = total > 0 ? Math.min(1, done / total) : 0;
  return (
    <div className="rounded-md border border-blue-200 bg-blue-50 p-3">
      <p aria-live="polite" role="status" className="mb-2 text-sm text-blue-900">
        Run is {status}: {done} / {total || "?"} cases done. Refreshing every 1.5 s.
      </p>
      <div
        role="progressbar"
        aria-label="Run progress"
        aria-valuemin={0}
        aria-valuemax={total || 0}
        aria-valuenow={done}
        className="h-2.5 w-full overflow-hidden rounded bg-blue-100"
      >
        <div className="h-full bg-blue-600 transition-all" style={{ width: `${ratio * 100}%` }} />
      </div>
    </div>
  );
}
