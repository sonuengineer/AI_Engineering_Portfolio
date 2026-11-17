import { ApiError, api, setToken, setUnauthorizedHandler } from "./client";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
}

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setUnauthorizedHandler(null);
  });

  it("parses the error envelope into ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(422, { error: { code: "validation_error", message: "bad input", request_id: "req-123" } })),
    );
    const err = await api("/api/v1/runs").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const e = err as ApiError;
    expect(e.status).toBe(422);
    expect(e.code).toBe("validation_error");
    expect(e.message).toBe("bad input");
    expect(e.requestId).toBe("req-123");
  });

  it("falls back to status text and x-request-id for non-JSON errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>bad gateway</html>", { status: 502, headers: { "x-request-id": "rid-9" } })));
    const e = (await api("/api/v1/x").catch((x: unknown) => x)) as ApiError;
    expect(e.code).toBe("http_502");
    expect(e.requestId).toBe("rid-9");
  });

  it("sends the bearer token and query params, and calls the 401 handler", async () => {
    setToken("tok-abc");
    const onUnauth = vi.fn();
    setUnauthorizedHandler(onUnauth);
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      jsonResponse(401, { error: { code: "unauthorized", message: "expired", request_id: "r1" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(api("/api/v1/runs", { query: { project_id: "p1", empty: "" } })).rejects.toBeInstanceOf(ApiError);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/runs?project_id=p1");
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer tok-abc");
    expect(onUnauth).toHaveBeenCalledOnce();
  });
});
