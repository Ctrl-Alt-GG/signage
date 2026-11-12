import { act, render, screen } from "@testing-library/react";
import { onlineManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Bundle } from "./api/client";
import { App } from "./App";
import { makeAnnouncement, makeBundle, makePass } from "./test-helpers";

type Answer = { status: number; body: unknown } | "unreachable";

/** Serves the bundle requests from a list of answers, repeating the last one. */
function serve(...answers: Answer[]) {
  const fetchMock = vi.fn(async () => {
    const answer = answers.length > 1 ? answers.shift() : answers[0];
    if (answer === undefined || answer === "unreachable") throw new TypeError("Failed to fetch");
    return new Response(JSON.stringify(answer.body), {
      status: answer.status,
      headers: { "content-type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const ok = (bundle: Bundle): Answer => ({ status: 200, body: bundle });

function renderApp(path = "/display/main/") {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/display/:slug" element={<App apiBase="/api/v1/" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function wait(ms: number) {
  await act(() => vi.advanceTimersByTimeAsync(ms));
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  onlineManager.setOnline(true);
});

describe("App", () => {
  it("shows the rotation on the background the bundle names", async () => {
    serve(ok(makeBundle()));
    renderApp();
    expect(await screen.findByRole("heading", { name: "Cím welcome" })).toBeInTheDocument();
    const stage = document.querySelector<HTMLElement>("[data-stage]");
    // The address carries the version of the artwork, so a new upload reaches the screen.
    expect(stage?.style.backgroundImage).toContain("/api/v1/display/background.svg?v=bundled");
  });

  it("says which screen is unknown instead of showing an empty background", async () => {
    const fetchMock = serve({ status: 404, body: { detail: "Unknown screen" } });
    renderApp("/display/lobby/");
    expect(await screen.findByText("Ismeretlen kijelző: lobby")).toBeInTheDocument();
    expect(screen.getByText("Unknown screen")).toBeInTheDocument();
    // The answer will not change by asking again at once.
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("tells an organizer to sign in for a preview", async () => {
    serve({ status: 403, body: { detail: "Sign in to the admin to preview a slide." } });
    renderApp("/display/main/?preview=food&lang=hu");
    expect(await screen.findByText("Sign in to the admin to preview a slide.")).toBeInTheDocument();
  });

  it("lets a takeover replace the slides and keeps a bar beneath them", async () => {
    const bar = makeAnnouncement({ id: "1" });
    const takeover = makeAnnouncement({
      id: "2",
      level: "urgent",
      takeover: true,
      text: { hu: "Hagyd el az épületet.", en: "Leave the building." },
    });
    serve(ok(makeBundle({ announcements: [bar] })), ok(makeBundle({ announcements: [takeover, bar] })));
    vi.useFakeTimers();
    renderApp();
    await wait(100);
    expect(screen.getByRole("heading", { name: "Cím welcome" })).toBeInTheDocument();
    expect(screen.getByText("Pizza 19:00-kor")).toBeInTheDocument();

    await wait(20_000);
    expect(screen.getByRole("alert")).toHaveTextContent("Hagyd el az épületet.");
    expect(screen.queryByRole("heading", { name: "Cím welcome" })).not.toBeInTheDocument();
    expect(screen.queryByText("Pizza 19:00-kor")).not.toBeInTheDocument();
  });

  it("takes an announcement off the screen when it ends, without waiting for the server", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-03T18:00:00+02:00"));
    const ending = makeAnnouncement({ ends_at: "2026-10-03T18:00:08+02:00" });
    serve(ok(makeBundle({ announcements: [ending] })), "unreachable");
    renderApp();
    await wait(100);
    expect(screen.getByText("Pizza 19:00-kor")).toBeInTheDocument();
    await wait(10_000);
    expect(screen.queryByText("Pizza 19:00-kor")).not.toBeInTheDocument();
  });

  it("replaces an informational takeover as soon as an urgent bar arrives", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-03T18:00:00+02:00"));
    const info = makeAnnouncement({
      id: "info", takeover: true, text: { hu: "Információ", en: "Information" },
    });
    const urgent = makeAnnouncement({
      id: "urgent", level: "urgent", takeover: false,
      text: { hu: "Vészjelzés", en: "Urgent safety" }, ends_at: "2026-10-03T18:00:35+02:00",
    });
    serve(
      ok(makeBundle({ announcements: [info] })),
      ok(makeBundle({ announcements: [info, urgent], clock: { now: "2026-10-03T18:00:20+02:00", timezone: "Europe/Budapest" } })),
      "unreachable",
    );
    renderApp();
    await wait(100);
    expect(screen.getByRole("alert")).toHaveTextContent("Információ");
    await wait(20_000);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(document.querySelector('[data-chrome="announcement"]')).toHaveTextContent("Vészjelzés");
    await wait(8_000);
    expect(document.querySelector('[data-chrome="announcement"]')).toHaveTextContent("Vészjelzés");
    await wait(12_000);
    expect(screen.getByRole("alert")).toHaveTextContent("Információ");
    expect(screen.queryByText("Vészjelzés")).toBeNull();
  });

  it("says so when the server is gone, and stops showing what can no longer be true", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-03T18:00:00+02:00"));
    const passes = [
      makePass("welcome"),
      makePass("now_next", { layout: "now_next", source: "live:schedule", live: null }),
    ];
    serve(ok(makeBundle({ passes })), "unreachable");
    renderApp();
    await wait(100);
    expect(document.querySelector('[data-slide="now_next"]')).not.toBeNull();
    expect(document.querySelector('[data-chrome="offline"]')).toBeNull();

    await wait(2 * 60_000);
    expect(document.querySelector('[data-chrome="offline"]')).toHaveTextContent("offline");
    // The schedule's "now" is from before the connection went. The plain slides stay.
    await wait(5 * 60_000);
    expect(document.querySelector('[data-slide="now_next"]')).toBeNull();
    expect(screen.getByRole("heading", { name: "Cím welcome" })).toBeInTheDocument();
  });

  it("expires live slides when the browser pauses polling because it is offline", async () => {
    vi.useFakeTimers();
    const passes = [
      makePass("welcome"),
      makePass("now_next", { layout: "now_next", source: "live:schedule", live: null }),
    ];
    serve(ok(makeBundle({ passes })));
    renderApp();
    await wait(100);
    onlineManager.setOnline(false);
    await wait(6 * 60_000);
    expect(document.querySelector('[data-chrome="offline"]')).not.toBeNull();
    expect(document.querySelector('[data-slide="now_next"]')).toBeNull();
    expect(screen.getByRole("heading", { name: "Cím welcome" })).toBeInTheDocument();
  });
});
