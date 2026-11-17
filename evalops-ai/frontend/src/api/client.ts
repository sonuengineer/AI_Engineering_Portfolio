// Typed fetch wrapper. All backend errors use {"error":{"code","message","request_id"}}.

const TOKEN_KEY = "evalops.token";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage unavailable: token lives only for this page load
  }
}

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

/** Registered by AuthProvider so any 401 logs the user out and redirects to /login. */
export function setUnauthorizedHandler(fn: UnauthorizedHandler | null): void {
  onUnauthorized = fn;
}

/** Turn a non-2xx response into an ApiError, parsing the backend error envelope when present. */
export async function parseError(res: Response): Promise<ApiError> {
  let code = `http_${res.status}`;
  let message = res.statusText || `Request failed with status ${res.status}`;
  let requestId: string | null = res.headers.get("x-request-id");
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "error" in body) {
      const err = (body as { error: { code?: string; message?: string; request_id?: string } }).error;
      if (err.code) code = err.code;
      if (err.message) message = err.message;
      if (err.request_id) requestId = err.request_id;
    } else if (body && typeof body === "object" && "detail" in body) {
      message = String((body as { detail: unknown }).detail);
    }
  } catch {
    // non-JSON body (e.g. proxy error page): keep the status text
  }
  return new ApiError(res.status, code, message, requestId);
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = path.startsWith("/") ? path : `/api/v1/${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function raw(path: string, opts: RequestOptions = {}): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) {
    body = opts.body;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), { method: opts.method ?? "GET", headers, body, signal: opts.signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "network_error", "Could not reach the API server", null);
  }
  if (!res.ok) {
    const err = await parseError(res);
    if (res.status === 401 && token && onUnauthorized) onUnauthorized();
    throw err;
  }
  return res;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await raw(path, opts);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Fetch an authenticated file and trigger a browser download. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const res = await raw(path);
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}
