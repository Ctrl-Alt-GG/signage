import type { ReactNode } from "react";

import type { Bilingual, Lang, PassLang } from "../api/client";

export function pick(text: Bilingual | undefined | null, lang: Lang): string {
  if (!text) return "";
  return text[lang] || text.hu || "";
}

export const UI = {
  hu: {
    stale: "frissítés folyamatban",
    nothing: "Nincs megjeleníthető tartalom.",
    now: "Most",
    next: "Következik",
    later: "Később",
    days: "nap",
    hours: "óra",
    minutes: "perc",
    seconds: "mp",
    live: "élő",
    audio: "hang",
    more: (n: number) => `+${n} további a servers.ctrl-alt-gg.hu oldalon`,
    started: "Elkezdődött!",
  },
  en: {
    stale: "data may be stale",
    nothing: "Nothing to show.",
    now: "Now",
    next: "Next",
    later: "Later",
    days: "days",
    hours: "hours",
    minutes: "minutes",
    seconds: "sec",
    live: "live",
    audio: "audio",
    more: (n: number) => `+${n} more at servers.ctrl-alt-gg.hu`,
    started: "We are live!",
  },
} as const;

export function primaryLang(lang: PassLang): Lang {
  return lang === "en" ? "en" : "hu";
}

/** "Magyar · English" on one line for labels; the English half is dropped when identical. */
export function joined(text: Bilingual | undefined | null, lang: PassLang): string {
  if (!text) return "";
  if (lang !== "both") return pick(text, lang);
  const hu = pick(text, "hu");
  const en = text.en && text.en !== text.hu ? text.en : "";
  return en ? `${hu} · ${en}` : hu;
}

/** Renders a bilingual string: one language, or Hungarian with English stacked beneath. */
export function Text({
  text,
  lang,
  className = "",
  secondaryClassName = "",
  as: Tag = "span",
}: {
  text: Bilingual | undefined | null;
  lang: PassLang;
  className?: string;
  secondaryClassName?: string;
  as?: "span" | "p" | "h1" | "h2" | "h3" | "div";
}): ReactNode {
  if (!text) return null;
  if (lang !== "both") {
    const value = pick(text, lang);
    return value ? <Tag className={className}>{value}</Tag> : null;
  }
  const hu = pick(text, "hu");
  const en = text.en && text.en !== text.hu ? text.en : "";
  if (!hu) return null;
  return (
    <Tag className={className}>
      <span className="block">{hu}</span>
      {en ? (
        <span className={`block text-[0.72em] text-ink-muted ${secondaryClassName}`}>{en}</span>
      ) : null}
    </Tag>
  );
}
