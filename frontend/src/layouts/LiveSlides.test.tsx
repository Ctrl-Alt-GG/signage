import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MatchRow, ScheduleEntryView, StreamsLive } from "../api/client";
import { makePass } from "../test-helpers";
import { ScheduleSlide } from "./ScheduleSlide";
import { ServersSlide } from "./ServersSlide";
import { StreamsSlide } from "./StreamsSlide";
import { TournamentSlide } from "./TournamentSlide";

const UNAVAILABLE = "Az élő adások listája most nem érhető el.";

function many<T>(count: number, make: (n: number) => T): T[] {
  return Array.from({ length: count }, (_, index) => make(index + 1));
}

function channel(n: number) {
  return { id: `stage-${n}`, name: `Stage ${n}`, audio_only: false, thumbnail_url: "", watch_url: "" };
}

function streams(live: StreamsLive, lang: "hu" | "both" = "hu") {
  return makePass("streams_live", { source: "live:streams", layout: "streams", lang, live });
}

function server(n: number) {
  return {
    name: `Server ${n}`, info: "", game_slug: "cs2", game_name: "Counter-Strike 2",
    game_short: "CS2", color_bg: "#000000", color_text: "#ffffff", players_text: `${n}/10`,
  };
}

function match(n: number, status: MatchRow["status"]): MatchRow {
  return {
    id: n, team1: `Team ${n}A`, team2: `Team ${n}B`, score1: n, score2: 0,
    start_local: "20:00", round: "Round 1", status,
  };
}

function slot(n: number): ScheduleEntryView {
  return {
    time: `${10 + n}:00`, type: "play", label: "", title: { hu: `Slot ${n}`, en: `Slot ${n}` },
    note: { hu: "", en: "" }, game: null, starts_at: "2026-10-03T20:00:00+02:00",
  };
}

describe("StreamsSlide", () => {
  it("says that the live streams can't be listed while Streams can't check them", () => {
    render(<StreamsSlide pass={streams({ live: [], source_status: "unavailable", stale: true })} />);
    expect(screen.getByText(UNAVAILABLE)).toBeInTheDocument();
    expect(screen.queryByText("Nincs megjeleníthető tartalom.")).not.toBeInTheDocument();
    expect(screen.queryByText("frissítés folyamatban")).not.toBeInTheDocument();
  });

  it("says the same when Streams has not answered at all", () => {
    render(<StreamsSlide pass={streams({ empty: true, stale: true }, "both")} />);
    expect(screen.getByText(UNAVAILABLE)).toBeInTheDocument();
    expect(screen.getByText("The list of live streams is not available right now.")).toBeInTheDocument();
  });

  it("marks the channels it last confirmed as not current", () => {
    render(<StreamsSlide pass={streams({ live: [channel(1)], source_status: "unavailable", stale: true })} />);
    expect(screen.getByText("Stage 1")).toBeInTheDocument();
    expect(screen.getByText("frissítés folyamatban")).toBeInTheDocument();
  });

  it("shows its empty text when Streams confirms that nothing is live", () => {
    render(<StreamsSlide pass={streams({ live: [], source_status: "fresh", stale: false })} />);
    expect(screen.getByText("Nincs megjeleníthető tartalom.")).toBeInTheDocument();
    expect(screen.queryByText(UNAVAILABLE)).not.toBeInTheDocument();
  });

  it("shows four channels and counts the others", () => {
    render(<StreamsSlide pass={streams({ live: many(9, channel), source_status: "fresh", stale: false })} />);
    expect(screen.getByText("Stage 4")).toBeInTheDocument();
    expect(screen.queryByText("Stage 5")).not.toBeInTheDocument();
    expect(screen.getByText("+5 további adás")).toBeInTheDocument();
  });
});

describe("long live lists", () => {
  it("shows eight servers and counts the others", () => {
    const live = { servers: many(12, server), stale: false };
    render(<ServersSlide pass={makePass("servers", { source: "live:projectile", layout: "servers", live })} />);
    expect(screen.getByText("Server 8")).toBeInTheDocument();
    expect(screen.queryByText("Server 9")).not.toBeInTheDocument();
    expect(screen.getByText("+4 további szerver")).toBeInTheDocument();
  });

  it("shows four upcoming matches and three results", () => {
    const live = {
      live: [],
      upcoming: many(10, (n) => match(n, "scheduled")),
      results: many(6, (n) => match(100 + n, "finished")),
      stale: false,
    };
    render(<TournamentSlide pass={makePass("tournament", { source: "live:bracket", layout: "tournament", live })} />);
    expect(screen.getByText("Team 4A")).toBeInTheDocument();
    expect(screen.queryByText("Team 5A")).not.toBeInTheDocument();
    expect(screen.getByText("Team 103A")).toBeInTheDocument();
    expect(screen.queryByText("Team 104A")).not.toBeInTheDocument();
  });

  it("says first that a match past its planned time awaits its result", () => {
    const live = { live: [match(1, "awaiting")], upcoming: [], results: [], stale: false };
    const pass = makePass("tournament", { source: "live:bracket", layout: "tournament", lang: "both", live });
    render(<TournamentSlide pass={pass} />);
    expect(screen.getByText("eredményre vár · awaiting result · Round 1 20:00")).toBeInTheDocument();
  });

  it("lists six slots of a long schedule", () => {
    const live = { now: [], next: [], later: [], upcoming: many(12, slot) };
    render(<ScheduleSlide pass={makePass("schedule", { source: "live:schedule", layout: "schedule", live })} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
    expect(screen.getByText("Slot 6")).toBeInTheDocument();
    expect(screen.queryByText("Slot 7")).not.toBeInTheDocument();
  });
});
