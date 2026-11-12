import type { Announcement, Bundle, Pass } from "./api/client";

/** A static list slide, which needs nothing but its text. */
export function makePass(slide: string, overrides: Partial<Pass> = {}): Pass {
  return {
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
    live: null,
    ...overrides,
  };
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
