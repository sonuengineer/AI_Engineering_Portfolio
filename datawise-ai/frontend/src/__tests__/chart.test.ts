import { describe, expect, it } from "vitest";
import { toChartData } from "../components/ResultChart";
import { formatCell } from "../components/format";

describe("toChartData", () => {
  it("maps a time series and formats periods", () => {
    const { data, keys } = toChartData({ type: "line", x: "month", y: ["revenue"], series: null }, ["month", "revenue"],
      [["2025-01-01", 10], ["2025-02-01", 20]]);
    expect(keys).toEqual(["revenue"]);
    expect(data).toEqual([{ month: "2025-01", revenue: 10 }, { month: "2025-02", revenue: 20 }]);
  });

  it("pivots a second dimension into series", () => {
    const { data, keys } = toChartData({ type: "line", x: "month", y: ["revenue"], series: "category" },
      ["month", "category", "revenue"], [["2025-01-01", "A", 1], ["2025-01-01", "B", 2], ["2025-02-01", "A", 3]]);
    expect(keys).toEqual(["A", "B"]);
    expect(data[0]).toEqual({ month: "2025-01", A: 1, B: 2 });
  });
});

describe("formatCell", () => {
  it("formats metrics by type", () => {
    expect(formatCell("conversion_rate", 0.1234)).toBe("12.3%");
    expect(formatCell("revenue", 1234.5)).toBe("$1,234.50");
    expect(formatCell("quarter", "2025-07-01")).toBe("2025-Q3");
    expect(formatCell("x", null)).toBe("--");
  });
});
