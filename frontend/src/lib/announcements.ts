import type { Announcement } from "../api/client";

const severity = { info: 0, warning: 1, urgent: 2 } as const;

/** Severity takes precedence over display mode. Lower-priority announcements wait
    while a more important one is active; among peers, a takeover takes the screen,
    otherwise their bars rotate. */
export function announcementDisplay(announcements: Announcement[]): {
  takeover: Announcement | null;
  bars: Announcement[];
} {
  const highest = Math.max(-1, ...announcements.map((item) => severity[item.level]));
  const peers = announcements.filter((item) => severity[item.level] === highest);
  const takeover = peers.find((item) => item.takeover) ?? null;
  return { takeover, bars: takeover ? [] : peers };
}
