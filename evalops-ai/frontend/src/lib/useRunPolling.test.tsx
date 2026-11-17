import { act, render, screen } from "@testing-library/react";
import { POLL_MS, useRunPolling } from "./useRunPolling";

function Probe() {
  const { run } = useRunPolling("r1");
  return <p>{run ? `${run.status} ${run.progress_done}/${run.progress_total}` : "none"}</p>;
}

function runBody(status: string, done: number) {
  return JSON.stringify({ id: "r1", status, progress_done: done, progress_total: 3 });
}

describe("useRunPolling", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("polls until the run reaches a terminal status, then stops", async () => {
    vi.useFakeTimers();
    const bodies = [runBody("queued", 0), runBody("running", 2), runBody("completed", 3)];
    const fetchMock = vi.fn(async () => new Response(bodies.shift() ?? runBody("completed", 3), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<Probe />);
    await act(async () => {});
    expect(screen.getByText("queued 0/3")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    expect(screen.getByText("running 2/3")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    expect(screen.getByText("completed 3/3")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS * 4);
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
