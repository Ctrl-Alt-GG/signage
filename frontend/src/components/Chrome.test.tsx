import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeAnnouncement } from "../test-helpers";
import { AnnouncementBar, Takeover, barPages } from "./Chrome";

const LONG_HU = "Hálózati karbantartás 22:00 és 22:30 között az egész épületben. " + "x".repeat(60);
const LONG_EN = "Network maintenance between 22:00 and 22:30 in the whole building. " + "y".repeat(60);

afterEach(() => {
  vi.useRealTimers();
});

describe("barPages", () => {
  it("shows a short announcement in both languages at once", () => {
    const pages = barPages([makeAnnouncement()]);
    expect(pages.map((page) => page.langs)).toEqual([["hu", "en"]]);
  });

  it("gives each language of a long announcement the bar to itself", () => {
    const long = makeAnnouncement({ text: { hu: LONG_HU, en: LONG_EN } });
    expect(barPages([long]).map((page) => page.langs)).toEqual([["hu"], ["en"]]);
  });

  it("shows a text once when there is no separate English", () => {
    const same = makeAnnouncement({ text: { hu: "GG", en: "GG" } });
    const missing = makeAnnouncement({ text: { hu: "Csak magyarul", en: "" } });
    expect(barPages([same, missing]).map((page) => page.langs)).toEqual([["hu"], ["hu"]]);
  });
});

describe("AnnouncementBar", () => {
  it("shows every announcement in turn, so a second one does not wait for the first", () => {
    vi.useFakeTimers();
    const first = makeAnnouncement({ id: "1", level: "warning" });
    const second = makeAnnouncement({ id: "2", text: { hu: "Talált kulcs", en: "Found keys" } });
    render(<AnnouncementBar announcements={[first, second]} />);
    expect(screen.getByText("Pizza 19:00-kor")).toBeInTheDocument();
    expect(screen.queryByText("Talált kulcs")).not.toBeInTheDocument();

    act(() => vi.advanceTimersByTime(8000));
    expect(screen.getByText("Talált kulcs")).toBeInTheDocument();
    expect(screen.getByText("Found keys")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(8000));
    expect(screen.getByText("Pizza 19:00-kor")).toBeInTheDocument();
  });

  it("shows a long text whole, one language after the other", () => {
    vi.useFakeTimers();
    const long = makeAnnouncement({ text: { hu: LONG_HU, en: LONG_EN } });
    render(<AnnouncementBar announcements={[long]} />);
    expect(screen.getByText(LONG_HU)).toBeInTheDocument();
    expect(screen.queryByText(LONG_EN)).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(8000));
    expect(screen.getByText(LONG_EN)).toBeInTheDocument();
  });

  it("stays put with a single short announcement", () => {
    vi.useFakeTimers();
    render(<AnnouncementBar announcements={[makeAnnouncement()]} />);
    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByText("Pizza 19:00-kor")).toBeInTheDocument();
    expect(screen.getByText("Pizza at 19:00")).toBeInTheDocument();
  });
});

describe("Takeover", () => {
  it("shows all of a long text instead of cutting it after two lines", () => {
    const text = { hu: "Hagyd el az épületet. ".repeat(13), en: "Leave the building. ".repeat(15) };
    render(<Takeover announcement={makeAnnouncement({ takeover: true, level: "urgent", text })} />);
    const hungarian = screen.getByText(text.hu.trim());
    expect(hungarian).toBeInTheDocument();
    expect(screen.getByText(text.en.trim())).toBeInTheDocument();
    // The text is fitted to the box by its size, never clamped to a number of lines.
    expect(hungarian.closest("[data-fit-text]")).not.toBeNull();
    expect(document.querySelector(".clamp-2")).toBeNull();
  });
});
