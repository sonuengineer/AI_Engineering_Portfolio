import { layoutSpans, parseIsoMs } from "./spanLayout";
import { span } from "../test/fixtures";

describe("parseIsoMs", () => {
  it("keeps microsecond precision", () => {
    const a = parseIsoMs("2026-01-01T00:00:00.000100Z");
    const b = parseIsoMs("2026-01-01T00:00:00.000350Z");
    expect(b - a).toBeCloseTo(0.25, 6);
  });
});

describe("layoutSpans", () => {
  const T0 = "2026-01-01T00:00:00.000000Z";
  const spans = [
    // deliberately out of order
    span("eval", null, "2026-01-01T00:00:00.008000Z", 2, "eval"),
    span("child", "root", "2026-01-01T00:00:00.002000Z", 3, "model_call"),
    span("root", null, T0, 6, "tool"),
    span("grandchild", "child", "2026-01-01T00:00:00.003000Z", 1, "http"),
  ];

  it("orders spans as a tree and computes depth", () => {
    const { rows } = layoutSpans(spans, T0, 10);
    expect(rows.map((r) => [r.span.id, r.depth])).toEqual([
      ["root", 0],
      ["child", 1],
      ["grandchild", 2],
      ["eval", 0],
    ]);
  });

  it("computes offsets and percentages relative to trace start", () => {
    const { rows, totalMs } = layoutSpans(spans, T0, 10);
    expect(totalMs).toBe(10);
    const child = rows.find((r) => r.span.id === "child")!;
    expect(child.offsetMs).toBeCloseTo(2, 6);
    expect(child.leftPct).toBeCloseTo(20, 6);
    expect(child.widthPct).toBeCloseTo(30, 6);
  });

  it("treats spans with a missing parent as roots and handles empty input", () => {
    const { rows } = layoutSpans([span("orphan", "nope", T0, 1)]);
    expect(rows[0].depth).toBe(0);
    expect(layoutSpans([]).rows).toEqual([]);
  });
});
