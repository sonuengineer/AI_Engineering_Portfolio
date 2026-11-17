import type { ReactNode } from "react";
import { ApiError } from "../api/client";

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <p role="status" aria-live="polite" className="py-6 text-sm text-slate-600">
      {label}...
    </p>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error);
  const requestId = error instanceof ApiError ? error.requestId : null;
  const code = error instanceof ApiError ? error.code : null;
  return (
    <div role="alert" className="my-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
      <p className="font-medium">
        {code ? `${code}: ` : ""}
        {message}
      </p>
      {requestId && (
        <p className="mt-1 text-xs text-red-800">
          request_id: <code className="break-all">{requestId}</code>
        </p>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded border border-red-400 bg-white px-2 py-1 text-xs font-medium text-red-900 hover:bg-red-100"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-600">{children}</p>;
}

interface DataStateProps<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload?: () => void;
  isEmpty?: (d: T) => boolean;
  empty?: ReactNode;
  loadingLabel?: string;
  children: (d: T) => ReactNode;
}

/** Renders loading / error / empty / content for an async resource. */
export function DataState<T>({ data, error, loading, reload, isEmpty, empty, loadingLabel, children }: DataStateProps<T>) {
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading && data === undefined) return <Loading label={loadingLabel} />;
  if (data === undefined) return null;
  if (isEmpty?.(data)) return <Empty>{empty ?? "Nothing here yet."}</Empty>;
  return <>{children(data)}</>;
}
