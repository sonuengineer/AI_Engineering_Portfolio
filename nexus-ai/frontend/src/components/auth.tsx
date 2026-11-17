import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, post, tokenStore } from "../api/client";
import type { Me } from "../api/types";

interface AuthState { me: Me | null; loading: boolean; login: (email: string, password: string) => Promise<void>; logout: () => void }
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));
  useEffect(() => {
    if (!tokenStore.get()) return;
    api<Me>("/auth/me").then(setMe).catch(() => tokenStore.clear()).finally(() => setLoading(false));
  }, []);
  const login = useCallback(async (email: string, password: string) => {
    const t = await post<{ access_token: string }>("/auth/login", { email, password });
    tokenStore.set(t.access_token);
    setMe(await api<Me>("/auth/me"));
  }, []);
  const logout = useCallback(() => { tokenStore.clear(); setMe(null); }, []);
  return <Ctx.Provider value={{ me, loading, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}

export const ROLE_RANK: Record<string, number> = { viewer: 0, analyst: 1, manager: 2, admin: 3 };
export const hasRole = (me: Me | null, role: string) => !!me && (ROLE_RANK[me.role] ?? -1) >= (ROLE_RANK[role] ?? 99);
