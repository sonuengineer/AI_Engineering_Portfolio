// Typed API client. The token lives in sessionStorage (cleared when the tab closes).
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) {
    super(message);
  }
}

const TOKEN_KEY = "nexus_token";
export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (t: string) => sessionStorage.setItem(TOKEN_KEY, t),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the NEXUS API. Is the backend running on port 8101?");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    if (res.status === 401) tokenStore.clear();
    throw new ApiError(res.status, err.code ?? "error", err.message ?? `Request failed (${res.status})`, err.request_id);
  }
  return body as T;
}

export const post = <T>(path: string, data?: unknown) =>
  api<T>(path, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data) });
