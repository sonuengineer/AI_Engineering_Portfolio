import type { AskResponse, Catalog, HistoryItem, Me, QueryPlan, SavedReport } from "./types";

const TOKEN_KEY = "datawise_token";

export class ApiError extends Error {
  status: number;
  code: string;
  requestId: string | null;
  constructor(status: number, code: string, message: string, requestId: string | null) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: token lives only for this page load */
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(path, { ...init, headers });
  if (res.status === 204) return undefined as T;
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const err = (body as { error?: { code?: string; message?: string; request_id?: string } } | null)?.error;
    if (res.status === 401 && path !== "/api/v1/auth/login") setToken(null);
    throw new ApiError(res.status, err?.code ?? "http_error", err?.message ?? `Request failed (${res.status})`,
      err?.request_id ?? res.headers.get("X-Request-ID"));
  }
  return body as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<Me>("/api/v1/auth/me"),
  ask: (question: string) =>
    request<AskResponse>("/api/v1/questions/ask", { method: "POST", body: JSON.stringify({ question }) }),
  history: () => request<HistoryItem[]>("/api/v1/history?limit=100"),
  reports: () => request<SavedReport[]>("/api/v1/reports"),
  createReport: (name: string, question: string, plan: QueryPlan) =>
    request<SavedReport>("/api/v1/reports", { method: "POST", body: JSON.stringify({ name, question, plan }) }),
  deleteReport: (id: number) => request<void>(`/api/v1/reports/${id}`, { method: "DELETE" }),
  runReport: (id: number) => request<AskResponse>(`/api/v1/reports/${id}/run`, { method: "POST" }),
  catalog: () => request<Catalog>("/api/v1/catalog"),
};
