import { afterEach, describe, expect, it, vi } from "vitest";

import { serverNow, syncClock } from "./clock";

afterEach(() => {
  vi.useRealTimers();
  syncClock(new Date().toISOString());
});

describe("the server's clock", () => {
  it("corrects a kiosk whose own clock is wrong", () => {
    vi.useFakeTimers();
    // The kiosk believes it is 17:48. The server knows it is 18:00.
    vi.setSystemTime(new Date("2026-10-03T17:48:00+02:00"));
    syncClock("2026-10-03T18:00:00+02:00");
    expect(new Date(serverNow()).toISOString()).toBe("2026-10-03T16:00:00.000Z");

    vi.advanceTimersByTime(90_000);
    expect(new Date(serverNow()).toISOString()).toBe("2026-10-03T16:01:30.000Z");
  });

  it("keeps the last known difference when an answer has no usable time", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-03T17:48:00+02:00"));
    syncClock("2026-10-03T18:00:00+02:00");
    syncClock("not a time");
    expect(new Date(serverNow()).toISOString()).toBe("2026-10-03T16:00:00.000Z");
  });
});
