import { useCallback, useEffect, useRef, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | undefined>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(undefined);
    try {
      setData(await fnRef.current());
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void reload(); }, deps);
  return { data, error, loading, reload, setData };
}
