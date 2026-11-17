import { render, screen } from "@testing-library/react";
import { MetricDeltaTable, classifyMetric } from "./CompareTable";
import { compareRow } from "../test/fixtures";

describe("compare table", () => {
  const rows = [
    compareRow({ metric: "answer_match", baseline_pass_rate: 1, candidate_pass_rate: 0.8, delta: -0.2, regression: true }),
    compareRow({ metric: "citations", baseline_pass_rate: 0.5, candidate_pass_rate: 0.9, delta: 0.4 }),
    compareRow({ metric: "keywords", delta: 0.01 }),
    compareRow({ metric: "judge", is_estimate: true, delta: -0.5, regression: true }),
  ];

  it("classifies regressions, improvements, and keeps estimates neutral", () => {
    expect(rows.map(classifyMetric)).toEqual(["regression", "improvement", "neutral", "neutral"]);
  });

  it("highlights regression rows red and improvement rows green", () => {
    render(<MetricDeltaTable rows={rows} />);
    const reg = screen.getByRole("rowheader", { name: /answer_match/ }).closest("tr")!;
    const imp = screen.getByRole("rowheader", { name: /citations/ }).closest("tr")!;
    const est = screen.getByRole("rowheader", { name: /judge/ }).closest("tr")!;
    expect(reg).toHaveClass("bg-red-50");
    expect(reg).toHaveTextContent("regression");
    expect(reg).toHaveTextContent("-20.0 pp");
    expect(imp).toHaveClass("bg-green-50");
    expect(est).not.toHaveClass("bg-red-50");
    expect(est).toHaveTextContent("estimate");
    expect(est).toHaveTextContent("non-gating");
  });
});
