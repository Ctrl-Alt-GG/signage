import { describe, expect, it } from "vitest";

import type { Announcement } from "../api/client";
import { makeAnnouncement } from "../test-helpers";
import { announcementDisplay } from "./announcements";

const levels = ["info", "warning", "urgent"] as const;
const variants = levels.flatMap((level) => [false, true].map((takeover) => ({ level, takeover })));
const cases = variants.flatMap((left) => variants.map((right) => ({
  name: `${left.level}/${left.takeover ? "takeover" : "bar"} with ${right.level}/${right.takeover ? "takeover" : "bar"}`,
  left,
  right,
})));

describe("announcementDisplay", () => {
  it("leaves an empty display empty", () => {
    expect(announcementDisplay([])).toEqual({ takeover: null, bars: [] });
  });

  it.each(cases)("gives severity precedence: $name", ({ left, right }) => {
    const rows = [makeAnnouncement({ id: "1", ...left }), makeAnnouncement({ id: "2", ...right })];
    const { takeover, bars } = announcementDisplay(rows);
    const shown: Announcement[] = takeover ? [takeover] : bars;
    const expectedLevel = rows.some((row) => row.level === "urgent") ? "urgent"
      : rows.some((row) => row.level === "warning") ? "warning" : "info";
    expect(shown.length).toBeGreaterThan(0);
    expect(shown.every((row) => row.level === expectedLevel)).toBe(true);
    const peers = rows.filter((row) => row.level === expectedLevel);
    if (peers.some((row) => row.takeover)) {
      expect(takeover?.takeover).toBe(true);
      expect(bars).toEqual([]);
    } else {
      expect(takeover).toBeNull();
      expect(bars).toEqual(peers);
    }
  });
});
