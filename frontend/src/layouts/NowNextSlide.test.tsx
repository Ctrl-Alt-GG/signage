import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ScheduleEntryView } from "../api/client";
import { makePass } from "../test-helpers";
import { NowNextSlide } from "./NowNextSlide";

function entry(title: string): ScheduleEntryView {
  return {
    time: "20:00",
    type: "play",
    label: "",
    title: { hu: title, en: title },
    note: { hu: "", en: "" },
    game: null,
    starts_at: "2026-10-03T20:00:00+02:00",
  };
}

describe("NowNextSlide", () => {
  it("shows two entries in a column, or one and the count of the others", () => {
    const pass = makePass("now_next", {
      layout: "now_next",
      source: "live:schedule",
      live: {
        now: ["Most", "Szintén most"].map(entry),
        next: [],
        later: ["Első", "Második", "Harmadik", "Negyedik"].map(entry),
        upcoming: [],
      },
    });
    render(<NowNextSlide pass={pass} />);
    expect(screen.getByText("Szintén most")).toBeInTheDocument();
    expect(screen.getByText("Első")).toBeInTheDocument();
    expect(screen.queryByText("Második")).not.toBeInTheDocument();
    expect(screen.getByText("+3 további program")).toBeInTheDocument();
    expect(screen.getAllByText(/további program/)).toHaveLength(1);
  });

  it("counts them in both languages on a bilingual pass", () => {
    const pass = makePass("now_next", {
      layout: "now_next",
      source: "live:schedule",
      lang: "both",
      live: { now: ["A", "B", "C"].map(entry), next: [], later: [], upcoming: [] },
    });
    render(<NowNextSlide pass={pass} />);
    expect(screen.getByText("+2 további program · +2 more")).toBeInTheDocument();
  });
});
