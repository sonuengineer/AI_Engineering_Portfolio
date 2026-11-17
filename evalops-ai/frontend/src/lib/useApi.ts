import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload: () => void;
}

/** Run an async loader whenever deps change; aborts and ignores stale responses. */
export function useApi<T>(loader: (signal: AbortSignal) => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    loaderRef.current(ctrl.signal)
      .then((d) => {
        if (!ctrl.signal.aborted) setData(d);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setError(e);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [...deps, tick]); // eslint-disable-line react-hooks/exhaustive-deps

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}
