import { useEffect, useState } from "react";
import { api } from "../api/client";
import { TERMINAL_STATUSES, type Run } from "../api/types";

export const POLL_MS = 1500;

/** Fetch a run and re-fetch every POLL_MS until it reaches a terminal status. */
export function useRunPolling(runId: string) {
  const [run, setRun] = useState<Run>();
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const r = await api<Run>(`/api/v1/runs/${runId}`, { signal: ctrl.signal });
        if (ctrl.signal.aborted) return;
        setRun(r);
        setError(null);
        if (!TERMINAL_STATUSES.includes(r.status)) timer = setTimeout(load, POLL_MS);
      } catch (e) {
        if (!ctrl.signal.aborted) setError(e);
      }
    };
    void load();
    return () => {
      ctrl.abort();
      if (timer) clearTimeout(timer);
    };
  }, [runId, tick]);

  return { run, error, loading: run === undefined && !error, reload: () => setTick((t) => t + 1) };
}
