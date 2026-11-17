import { render, screen } from "@testing-library/react";
import { MetricCard } from "./MetricCard";
import { metric } from "../test/fixtures";

describe("MetricCard", () => {
  it("shows an estimate badge for judge metrics", () => {
    render(<MetricCard name="judge_correctness" metric={metric({ is_estimate: true, gating: false })} />);
    expect(screen.getByText("estimate")).toBeInTheDocument();
    expect(screen.getByText("non-gating")).toBeInTheDocument();
  });

  it("has no estimate badge for deterministic metrics and formats pass rate", () => {
    render(<MetricCard name="answer_match" metric={metric()} />);
    expect(screen.queryByText("estimate")).not.toBeInTheDocument();
    expect(screen.getByText("75.0%")).toBeInTheDocument();
  });

  it("shows the skip reason when every case was skipped", () => {
    render(
      <MetricCard
        name="judge"
        metric={metric({ scored: 0, passed: 0, skipped: 5, pass_rate: null, mean: null, is_estimate: true })}
        skipReason="skipped: judge requires a configured LLM provider"
      />,
    );
    expect(screen.getByText("All cases skipped: judge requires a configured LLM provider")).toBeInTheDocument();
    // pass rate and mean are both unavailable
    expect(screen.getAllByText("--")).toHaveLength(2);
  });
});
