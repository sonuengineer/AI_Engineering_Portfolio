import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { LoginPage } from "./LoginPage";

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<p>home page</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("submits credentials, stores the token and navigates home", async () => {
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
      if (url === "/api/v1/auth/login") return new Response(JSON.stringify({ access_token: "t-1" }), { status: 200 });
      return new Response(JSON.stringify({ id: "u", org_id: "o", email: "a@b.c", display_name: "", role: "admin" }), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderLogin();
    await userEvent.type(screen.getByLabelText("Email"), "a@b.c");
    await userEvent.type(screen.getByLabelText("Password"), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("home page")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/auth/login");
    expect(JSON.parse(String(init?.body))).toEqual({ email: "a@b.c", password: "secret-pass" });
    expect(sessionStorage.getItem("evalops.token")).toBe("t-1");
  });

  it("shows the API error message and request id on bad credentials", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ error: { code: "invalid_credentials", message: "Invalid email or password", request_id: "rq-7" } }), {
          status: 401,
        }),
      ),
    );
    renderLogin();
    await userEvent.type(screen.getByLabelText("Email"), "a@b.c");
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Invalid email or password");
    expect(alert).toHaveTextContent("rq-7");
  });
});
