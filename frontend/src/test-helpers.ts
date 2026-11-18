import { vi } from "vitest";

import type { Announcement, Bundle, Pass, PassOf, StaticPass } from "./api/client";

type LiveSource = Exclude<Pass["source"], "static">;

/** A pass with the text of a list slide: a static list slide, or a live pass of the source,
    layout and live data the overrides name. */
export function makePass(slide: string, overrides?: Partial<StaticPass>): StaticPass;
export function makePass<S extends LiveSource>(
  slide: string,
  overrides: Partial<PassOf<S>> & Pick<PassOf<S>, "layout"> & { source: S },
): PassOf<S>;
export function makePass(slide: string, overrides: Partial<Pass> = {}): Pass {
  const pass: StaticPass = {
    key: `${slide}:hu`,
    slide,
    layout: "list",
    source: "static",
    lang: "hu",
    duration_ms: 5000,
    content: {
      kicker: { hu: "", en: "" },
      title: { hu: `Cím ${slide}`, en: `Title ${slide}` },
      body: { hu: "", en: "" },
      footer: { hu: "", en: "" },
      empty: { hu: "", en: "" },
      items: [],
      columns: [],
      labels: {},
      link: null,
    },
  };
  return { ...pass, ...overrides } as Pass;
}

export function makeAnnouncement(overrides: Partial<Announcement> = {}): Announcement {
  return {
    id: "1",
    level: "info",
    takeover: false,
    text: { hu: "Pizza 19:00-kor", en: "Pizza at 19:00" },
    ends_at: null,
    ...overrides,
  };
}

export function makeBundle(overrides: Partial<Bundle> = {}): Bundle {
  return {
    generated_at: "2026-10-03T18:00:00+02:00",
    screen: {
      slug: "main",
      name: "Main hall",
      refresh_seconds: 20,
      show_clock: true,
      show_progress: true,
      language_mode: "slide",
    },
    phase: null,
    clock: { now: "2026-10-03T18:00:00+02:00", timezone: "Europe/Budapest" },
    event: {
      name: "Ctrl-Alt-GG",
      tagline: "",
      starts_at: "2026-10-03T15:30:00+02:00",
      ends_at: "2026-10-04T08:00:00+02:00",
    },
    stage: {
      width: 1920,
      height: 1080,
      safe: { x: 96, y: 204, width: 1728, height: 564 },
      background_url: "/api/v1/display/background.svg?v=bundled",
    },
    announcements: [],
    passes: [makePass("welcome")],
    warnings: [],
    preview: false,
    ...overrides,
  };
}

/** A request that the server takes and never answers. Like a real one, it ends when it is
    aborted. */
export function hangingFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const signal = init?.signal ?? (input instanceof Request ? input.signal : undefined);
  return new Promise((_, reject) => {
    signal?.addEventListener("abort", () => reject(signal.reason));
  });
}

/** AbortSignal.timeout keeps its own time, which fake timers do not move. These signals
    keep it with setTimeout, so advancing the fake clock reaches them. */
export function fakeAbortTimeouts() {
  vi.spyOn(AbortSignal, "timeout").mockImplementation((ms) => {
    const controller = new AbortController();
    setTimeout(() => controller.abort(new DOMException("The request timed out.", "TimeoutError")), ms);
    return controller.signal;
  });
}
