import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnswerPanel } from "../components/AnswerPanel";
import type { AskResponse } from "../types";

function base(overrides: Partial<AskResponse>): AskResponse {
  return {
    status: "answered", plan: null, sql: null, validation: { ok: true, issues: [] }, columns: [], rows: [],
    row_count: 0, insight: null, clarification: null, rejection_reason: null, provider: "local", model: "rules-v1",
    latency_ms: 12, query_id: 1, chart: null, insight_provenance: [], ...overrides,
  };
}

describe("AnswerPanel", () => {
  it("shows the deterministic local adapter badge, SQL, validation, insight and rows", () => {
    render(
      <AnswerPanel question="q" result={base({
        sql: "SELECT 1 LIMIT 1", columns: ["product", "revenue"], rows: [["Webcam", 1234.5], ["Kite", 10]],
        row_count: 2, insight: "Highest revenue: Webcam at $1,234.50", chart: { type: "table", x: null, y: [], series: null },
        insight_provenance: [{ columns: ["product", "revenue"], row_indexes: [0], note: "max row" }],
      })} />,
    );
    expect(screen.getByText("Deterministic local adapter")).toBeInTheDocument();
    expect(screen.getByText("Validation passed")).toBeInTheDocument();
    expect(screen.getByText("SELECT 1 LIMIT 1")).toBeInTheDocument();
    expect(screen.getByTestId("insight")).toHaveTextContent("Webcam at $1,234.50");
    expect(screen.getByText("$1,234.50")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy sql/i })).toBeInTheDocument();
  });

  it("renders clarification options as buttons that resend the option", async () => {
    const onClarify = vi.fn();
    render(
      <AnswerPanel question="best customers" onClarify={onClarify} result={base({
        status: "needs_clarification",
        clarification: { question: "How should customers be ranked?", options: ["Top 10 customers by revenue", "Top 10 customers by order count"] },
      })} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Top 10 customers by order count" }));
    expect(onClarify).toHaveBeenCalledWith("Top 10 customers by order count");
  });

  it("shows the rejection reason and no result table", () => {
    render(<AnswerPanel question="x" result={base({ status: "rejected", rejection_reason: "DATAWISE is read-only" })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("DATAWISE is read-only");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("lists validation issues when validation failed", () => {
    render(<AnswerPanel question="x" result={base({ status: "rejected", sql: "SELECT", validation: { ok: false, issues: ["missing LIMIT"] } })} />);
    expect(screen.getByText("Validation failed")).toBeInTheDocument();
    expect(screen.getByText("missing LIMIT")).toBeInTheDocument();
  });
});
