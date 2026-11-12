import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Pass } from "../api/client";
import { makePass } from "../test-helpers";
import { Rotation } from "./Rotation";

function showing(onPassChange: ReturnType<typeof vi.fn>): string {
  return (onPassChange.mock.lastCall?.[0] as Pass | undefined)?.slide ?? "";
}

function rotation(passes: Pass[], onPassChange: (pass: Pass) => void) {
  return (
    <Rotation
      passes={passes}
      showProgress={false}
      frozen={false}
      empty={<p>nothing</p>}
      onPassChange={onPassChange}
    />
  );
}

async function wait(ms: number) {
  await act(() => vi.advanceTimersByTimeAsync(ms));
}

describe("Rotation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("shows each pass for its own duration", async () => {
    const onPassChange = vi.fn();
    const passes = [
      makePass("a", { duration_ms: 5000 }),
      makePass("b", { duration_ms: 9000 }),
      makePass("c", { duration_ms: 5000 }),
    ];
    render(rotation(passes, onPassChange));
    await wait(0);
    expect(showing(onPassChange)).toBe("a");
    await wait(4999);
    expect(showing(onPassChange)).toBe("a");
    await wait(1);
    expect(showing(onPassChange)).toBe("b");
    await wait(8999);
    expect(showing(onPassChange)).toBe("b");
    await wait(1);
    expect(showing(onPassChange)).toBe("c");
  });

  it("applies durations and passes that changed after the page loaded", async () => {
    const onPassChange = vi.fn();
    const first = [makePass("a"), makePass("b")];
    const view = render(rotation(first, onPassChange));
    await wait(0);

    // A phase change: the second pass got longer and a third one joined. These used to
    // be ignored until the page was reloaded, and the new pass flashed by.
    const second = [
      makePass("a"),
      makePass("b", { duration_ms: 20_000 }),
      makePass("c", { duration_ms: 7000 }),
    ];
    view.rerender(rotation(second, onPassChange));
    await wait(5000);
    expect(showing(onPassChange)).toBe("b");
    await wait(19_999);
    expect(showing(onPassChange)).toBe("b");
    await wait(1);
    expect(showing(onPassChange)).toBe("c");
    await wait(6999);
    expect(showing(onPassChange)).toBe("c");
    await wait(1);
    expect(showing(onPassChange)).toBe("a");
  });

  it("does not start a pass over when a poll brings the same passes again", async () => {
    const onPassChange = vi.fn();
    const view = render(rotation([makePass("a"), makePass("b")], onPassChange));
    await wait(3000);
    // Every answer is a new list of new objects, and arrives more often than a slide ends.
    view.rerender(rotation([makePass("a"), makePass("b")], onPassChange));
    await wait(1999);
    expect(showing(onPassChange)).toBe("a");
    await wait(1);
    expect(showing(onPassChange)).toBe("b");
  });

  it("shows all four live matches within one cycle without a poll restarting the pages", async () => {
    const page = (number: number, ids: number[]) => makePass("tournament_live", {
      key: `tournament_live:hu:page-${number}`,
      layout: "tournament",
      duration_ms: 5000,
      live: {
        live: ids.map((id) => ({ id, team1: `ALPHA-${id}`, team2: `BETA-${id}`, status: "live" })),
        live_page: { number, count: 2, first: ids[0], last: ids[1], total: 4 },
        upcoming: [], results: [], stale: false,
      },
    });
    const pages = () => [page(1, [1, 2]), page(2, [3, 4])];
    const onPassChange = vi.fn();
    const view = render(rotation(pages(), onPassChange));
    const currentPage = () => (onPassChange.mock.lastCall?.[0] as Pass).key;
    await wait(0);
    expect(currentPage()).toBe("tournament_live:hu:page-1");
    expect(screen.getAllByLabelText("Élő meccsek oldala")).toHaveLength(2);
    await wait(3000);
    view.rerender(rotation(pages(), onPassChange));
    await wait(2000);
    expect(currentPage()).toBe("tournament_live:hu:page-2");
    expect(screen.getByText("3-4 / 4")).toBeInTheDocument();
    await wait(5000);
    expect(currentPage()).toBe("tournament_live:hu:page-1");
    const seen = new Set(onPassChange.mock.calls.flatMap((call) => {
      const pass = call[0] as Pass;
      return (pass.live as { live: { id: number }[] }).live.map((match) => match.id);
    }));
    expect([...seen].sort()).toEqual([1, 2, 3, 4]);
  });

  it("stays on a single pass and on a preview", async () => {
    const onPassChange = vi.fn();
    render(rotation([makePass("only")], onPassChange));
    await wait(60_000);
    expect(showing(onPassChange)).toBe("only");

    const frozen = vi.fn();
    render(
      <Rotation
        passes={[makePass("a"), makePass("b")]}
        showProgress={false}
        frozen
        empty={null}
        onPassChange={frozen}
      />,
    );
    await wait(60_000);
    expect(showing(frozen)).toBe("a");
  });

  it("leaves out a pass that cannot be drawn instead of going dark", async () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    const onPassChange = vi.fn();
    // Live data is whatever the upstream sent. This is not a list of servers.
    const broken = makePass("servers", { layout: "servers", live: { servers: "none" } });
    const view = render(rotation([makePass("a"), broken, makePass("c")], onPassChange));
    await wait(0);

    expect(screen.getByRole("heading", { name: "Cím a" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cím c" })).toBeInTheDocument();
    expect(document.querySelector('[data-slide="servers"]')).toBeNull();
    expect(errors).toHaveBeenCalled();
    await wait(5000);
    expect(showing(onPassChange)).toBe("c");

    // The same answer again does not bring it back. A new one is another try.
    view.rerender(rotation([makePass("a"), broken, makePass("c")], onPassChange));
    await wait(0);
    expect(document.querySelector('[data-slide="servers"]')).toBeNull();
    const mended = makePass("servers", { layout: "servers", live: { servers: [], stale: false } });
    view.rerender(rotation([makePass("a"), mended, makePass("c")], onPassChange));
    await wait(0);
    expect(document.querySelector('[data-slide="servers"]')).not.toBeNull();
  });

  it("shows the empty state when no pass is left", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const broken = makePass("servers", { layout: "servers", live: { servers: 5 } });
    render(rotation([broken], vi.fn()));
    await wait(0);
    expect(screen.getByText("nothing")).toBeInTheDocument();
  });
});
