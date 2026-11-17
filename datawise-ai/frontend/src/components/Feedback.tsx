export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 py-6 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-teal-600" aria-hidden="true" />
      {label}...
    </div>
  );
}

export function ErrorBox({ message, requestId }: { message: string; requestId?: string | null }) {
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      {message}
      {requestId ? <span className="mt-1 block text-xs text-red-600">Request ID: {requestId}</span> : null}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-md border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">{children}</p>;
}
