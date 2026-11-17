import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth";
import { LoginPage } from "../pages/Login";

afterEach(() => vi.restoreAllMocks());

describe("LoginPage", () => {
  it("shows the API error message on bad credentials", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "invalid_credentials", message: "Invalid email or password", request_id: "r1" } }),
        { status: 401, headers: { "Content-Type": "application/json" } }),
    );
    render(<AuthProvider><MemoryRouter><LoginPage /></MemoryRouter></AuthProvider>);
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });
});
