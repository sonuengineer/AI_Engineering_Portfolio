import { useCallback, useState } from "react";

const KEY = "interview-progress-v1";
interface Progress { learned: Record<string, true>; bookmarked: Record<string, true> }
const EMPTY: Progress = { learned: {}, bookmarked: {} };

function load(): Progress {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return EMPTY;
    const p = JSON.parse(raw) as Partial<Progress>;
    return { learned: p.learned ?? {}, bookmarked: p.bookmarked ?? {} };
  } catch {
    return EMPTY; // storage blocked or corrupt -> progress simply is not persisted
  }
}

/** Local-only progress tracking (no account). Keys are question ids, namespaced by project. */
export function useProgress() {
  const [state, setState] = useState<Progress>(load);
  const toggle = useCallback((kind: keyof Progress, id: string) => {
    setState((prev) => {
      const nextKind = { ...prev[kind] };
      if (nextKind[id]) delete nextKind[id]; else nextKind[id] = true;
      const next = { ...prev, [kind]: nextKind };
      try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }, []);
  const reset = useCallback(() => {
    try { localStorage.removeItem(KEY); } catch { /* ignore */ }
    setState(EMPTY);
  }, []);
  return { ...state, toggle, reset };
}
