import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Approval, Me } from "../api/types";
import { ApprovalCard } from "./ApprovalCard";
import * as auth from "./auth";
import { Markdown } from "./Markdown";
import { ProviderBadge } from "./ui";

const me = (role: string): Me => ({ id: "u", email: "x@y", full_name: "X", role, org_id: "o", org_name: "Acme", llm_provider: "local", embedding_provider: "local" });
const approval: Approval = {
  id: "a1", run_id: "r1", action: "send_email", status: "pending", rationale: "Account review",
  payload: { to: "dana@northwind.example", subject: "Account review", body: "Hi Dana", customer_name: "Northwind" },
  decided_by: null, decided_at: null, decision_note: null, result: null, created_at: new Date().toISOString(),
};

afterEach(() => vi.restoreAllMocks());

describe("Markdown", () => {
  it("renders untrusted HTML as text, never as markup", () => {
    const { container } = render(<Markdown source={"# Title\n- EVIDENCE: <img src=x onerror=alert(1)>"} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
  });
});

describe("ProviderBadge", () => {
  it("labels the deterministic adapter honestly", () => {
    render(<ProviderBadge provider="local" />);
    expect(screen.getByText("Deterministic local adapter")).toBeInTheDocument();
  });
});

describe("ApprovalCard", () => {
  it("hides decision buttons from analysts", () => {
    vi.spyOn(auth, "useAuth").mockReturnValue({ me: me("analyst"), loading: false, login: vi.fn(), logout: vi.fn() });
    render(<ApprovalCard approval={approval} onChange={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
    expect(screen.getByText(/Only managers or admins/)).toBeInTheDocument();
  });

  it("lets managers approve with an edited subject", async () => {
    vi.spyOn(auth, "useAuth").mockReturnValue({ me: me("manager"), loading: false, login: vi.fn(), logout: vi.fn() });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ...approval, status: "executed" }), { status: 200, headers: { "content-type": "application/json" } }),
    );
    const onChange = vi.fn();
    render(<ApprovalCard approval={approval} onChange={onChange} />);
    const subject = screen.getByLabelText("Subject");
    await userEvent.clear(subject);
    await userEvent.type(subject, "New subject");
    await userEvent.click(screen.getByRole("button", { name: /approve and send/i }));
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/approvals/a1/approve", expect.objectContaining({ method: "POST" }));
    const sent = JSON.parse((fetchMock.mock.calls[0]![1] as RequestInit).body as string);
    expect(sent.subject).toBe("New subject");
    expect(sent.body).toBeNull();
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ status: "executed" }));
  });
});
