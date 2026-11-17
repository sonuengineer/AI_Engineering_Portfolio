import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExternalLink } from "./components/ExternalLink";
import { numericLeaves } from "./data/artifacts";
import type { Question } from "./data/interviewTypes";
import { QuestionCard } from "./pages/InterviewProject";

const q: Question = {
  id: "q1", topic: "overview", difficulty: "advanced", question: "Why use RRF?",
  answer: "Because it fuses ranks without calibrating scores.", reasoning: "Probes retrieval knowledge.",
  code_refs: ["backend/app/services/retrieval.py:hybrid_search"], follow_ups: ["What is k?"], kind: "implemented",
};

afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

describe("ExternalLink", () => {
  it("never renders a fake link for unconfigured placeholders", () => {
    render(<ExternalLink link={{ url: null, label: "Live demo" }} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("Live demo: not configured")).toBeInTheDocument();
  });
  it("renders a safe external link when configured", () => {
    render(<ExternalLink link={{ url: "https://example.com", label: "GitHub" }} />);
    const a = screen.getByRole("link", { name: /GitHub/ });
    expect(a).toHaveAttribute("rel", "noopener noreferrer");
  });
});

describe("numericLeaves", () => {
  it("only extracts real numeric values from artifacts", () => {
    expect(numericLeaves({ a: { p50: 1.5, label: "x" }, c: 3 })).toEqual([{ key: "a.p50", value: 1.5 }, { key: "c", value: 3 }]);
    expect(numericLeaves({ runs: [{ label: "NEXUS v2", rate: 0.5 }] })).toEqual([{ key: "runs[NEXUS v2].rate", value: 0.5 }]);
  });
});

describe("QuestionCard", () => {
  it("hides the answer until revealed and persists learned/bookmark state", async () => {
    render(<MemoryRouter><QuestionCard q={q} ns="nexus-ai" position="1 of 1" /></MemoryRouter>);
    expect(screen.queryByText(/fuses ranks/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Reveal answer" }));
    expect(screen.getByText(/fuses ranks/)).toBeInTheDocument();
    expect(screen.getByText("What is k?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark learned" }));
    expect(JSON.parse(localStorage.getItem("interview-progress-v1")!).learned["nexus-ai:q1"]).toBe(true);
    expect(screen.getByRole("button", { name: "Learned" })).toHaveAttribute("aria-pressed", "true");
  });

  it("still works when storage is unavailable", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    render(<MemoryRouter><QuestionCard q={q} ns="nexus-ai" position="1 of 1" /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: "Bookmark" }));
    expect(screen.getByRole("button", { name: "Bookmarked" })).toBeInTheDocument();
  });
});
