import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "../api/client";
import type { User } from "../api/types";

interface AuthValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  canWrite: boolean;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTok] = useState<string | null>(() => getToken());
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(() => getToken() !== null);

  const logout = useCallback(() => {
    setToken(null);
    setTok(null);
    setUser(null);
  }, []);

  // Any 401 from the API (expired/invalid token) logs out; RequireAuth then redirects to /login.
  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api<User>("/api/v1/auth/me")
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) logout();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, logout]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
    });
    setToken(res.access_token);
    setTok(res.access_token);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      token,
      loading,
      login,
      logout,
      canWrite: user?.role === "admin" || user?.role === "member",
    }),
    [user, token, loading, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
