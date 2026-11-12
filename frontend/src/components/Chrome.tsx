import { useState } from "react";
import { useInterval } from "usehooks-ts";

import { Clock } from "./Clock";
import { FitText } from "./FitText";
import type { Announcement, Lang, PassLang } from "../api/client";
import { UI, pick } from "../lib/i18n";

export function LangPill({ lang }: { lang: PassLang }) {
  if (lang === "both") return null;
  return (
    <span className="badge badge-outline h-[44px] border-ink-dim px-4 text-[26px] font-semibold uppercase text-ink-muted">
      {lang}
    </span>
  );
}

export function TopRight({
  showClock,
  timeZone,
  lang,
}: {
  showClock: boolean;
  timeZone: string;
  lang: PassLang;
}) {
  return (
    <div className="absolute right-0 top-[10px] flex items-center gap-4" data-chrome="top-right">
      <LangPill lang={lang} />
      {showClock ? <Clock timeZone={timeZone} lang={lang === "en" ? "en" : "hu"} /> : null}
    </div>
  );
}

export function Progress({ durationMs, passKey }: { durationMs: number; passKey: string }) {
  return (
    <div
      className="absolute bottom-0 left-0 h-[4px] w-full overflow-hidden rounded-full bg-ink-dim/30"
      data-chrome="progress"
    >
      <div
        key={passKey}
        className="h-full bg-brand-600/60"
        style={{ animation: `progress ${durationMs}ms linear forwards` }}
      />
      <style>{`@keyframes progress { from { width: 0% } to { width: 100% } }`}</style>
    </div>
  );
}

/** Says that the screen has lost the server, in words: what it shows may be out of date. */
export function OfflineNote({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <span
      className="absolute left-0 top-[10px] flex h-[44px] items-center gap-3 rounded-full border border-ink-dim px-4 text-[24px] font-medium text-ink-muted"
      data-chrome="offline"
      role="status"
    >
      <span className="block size-3 rounded-full bg-accent-400" aria-hidden />
      {UI.hu.offline} · {UI.en.offline}
    </span>
  );
}

const levelClass = {
  info: "bg-key-top text-ink border border-white/10",
  warning: "bg-accent-400 text-field",
  urgent: "bg-brand-600 text-ink",
} as const;

/* Both languages fit the bar side by side while they are short. A longer announcement is
   shown one language at a time, each with the bar to itself. */
const SHORT_ENOUGH_FOR_BOTH = 70;
const PAGE_MS = 8_000;

type BarPage = { announcement: Announcement; langs: Lang[] };

/** What the bar shows, in turn: every announcement, and a long one once per language. */
export function barPages(announcements: Announcement[]): BarPage[] {
  return announcements.flatMap((announcement) => {
    const hu = pick(announcement.text, "hu");
    const en = pick(announcement.text, "en");
    if (en === hu) return [{ announcement, langs: ["hu" as const] }];
    if (Math.max(hu.length, en.length) <= SHORT_ENOUGH_FOR_BOTH) {
      return [{ announcement, langs: ["hu" as const, "en" as const] }];
    }
    return [
      { announcement, langs: ["hu" as const] },
      { announcement, langs: ["en" as const] },
    ];
  });
}

export function AnnouncementBar({ announcements }: { announcements: Announcement[] }) {
  const pages = barPages(announcements);
  const [turn, setTurn] = useState(0);
  useInterval(() => setTurn((value) => value + 1), pages.length > 1 ? PAGE_MS : null);
  const page = pages[turn % pages.length];
  if (!page) return null;

  const { announcement, langs } = page;
  const both = langs.length > 1;
  return (
    <div
      className={`absolute bottom-[12px] left-0 flex h-[80px] w-full items-center rounded-[16px] px-8 ${levelClass[announcement.level]}`}
      data-chrome="announcement"
      role="status"
    >
      {/* The text is never cut off: it gets smaller until all of it is in the bar. */}
      <FitText
        max={34}
        min={16}
        watch={`${announcement.id}:${langs.join("+")}:${pick(announcement.text, "hu")}`}
        className="max-h-[76px] w-full py-[0.06em] font-semibold leading-[1.15]"
      >
        {both ? (
          <>
            <span className="block whitespace-nowrap">{pick(announcement.text, "hu")}</span>
            <span className="block whitespace-nowrap text-[0.76em] font-normal opacity-80">
              {pick(announcement.text, "en")}
            </span>
          </>
        ) : (
          <span className="block">{pick(announcement.text, langs[0] ?? "hu")}</span>
        )}
      </FitText>
    </div>
  );
}

export function Takeover({ announcement }: { announcement: Announcement }) {
  const hu = pick(announcement.text, "hu");
  const en = announcement.text.en !== hu ? pick(announcement.text, "en") : "";
  const border = {
    info: "border-ink-muted",
    warning: "border-accent-400",
    urgent: "border-brand-600",
  }[announcement.level];
  const tint = { info: "bg-key-top", warning: "bg-accent-400/15", urgent: "bg-brand-600/20" }[
    announcement.level
  ];
  return (
    <section
      // The top padding is the strip the clock sits in, so no line of text runs under it.
      className={`surface flex h-full w-full flex-col justify-center border-l-[12px] px-16 pb-8 pt-[68px] ${border} ${tint}`}
      data-chrome="takeover"
      role="alert"
    >
      {/* A takeover is what must be read: an evacuation, a match call. All of it is
          shown, in type as large as the screen has room for. */}
      {/* The padding is room for the letters that reach above and below their line. */}
      <FitText
        max={72}
        min={30}
        watch={`${announcement.id}:${hu}:${en}`}
        className="max-h-full py-[0.1em]"
      >
        <p className="font-extrabold leading-[1.1]">{hu}</p>
        {en ? (
          <p className="mt-[0.35em] text-[0.72em] font-semibold leading-[1.15] text-ink-muted">
            {en}
          </p>
        ) : null}
      </FitText>
    </section>
  );
}
