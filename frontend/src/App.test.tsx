import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Pass } from "./api/client";
import { SlidePass } from "./components/SlidePass";
import { Text } from "./lib/i18n";

const basePass: Pass = {
  key: "house_rules:hu",
  slide: "house_rules",
  layout: "list",
  source: "static",
  lang: "hu",
  duration_ms: 20000,
  content: {
    kicker: { hu: "", en: "" },
    title: { hu: "Házirend", en: "House rules" },
    body: { hu: "", en: "" },
    footer: { hu: "", en: "" },
    empty: { hu: "", en: "" },
    items: [
      { hu: "Csak fejhallgató.", en: "Headsets only.", icon: "" },
      { hu: "Nincs csalás.", en: "No cheating.", icon: "" },
    ],
    columns: [],
    labels: {},
    link: null,
  },
  live: null,
};

describe("SlidePass", () => {
  it("renders the Hungarian pass of a list slide", () => {
    render(<SlidePass pass={basePass} />);
    expect(screen.getByRole("heading", { name: "Házirend" })).toBeInTheDocument();
    expect(screen.getByText("Csak fejhallgató.")).toBeInTheDocument();
    expect(screen.queryByText("Headsets only.")).not.toBeInTheDocument();
  });

  it("stacks both languages when the pass language is both", () => {
    render(<SlidePass pass={{ ...basePass, key: "house_rules:both", lang: "both" }} />);
    expect(screen.getByText("House rules")).toBeInTheDocument();
    expect(screen.getByText("Headsets only.")).toBeInTheDocument();
  });

  it("falls back to Hungarian when the English text is empty", () => {
    render(<Text text={{ hu: "Szia", en: "" }} lang="en" />);
    expect(screen.getByText("Szia")).toBeInTheDocument();
  });
});
