import { Clock } from "./Clock";
import type { Announcement, PassLang } from "../api/client";
import { pick } from "../lib/i18n";

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

export function OfflineDot({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <span
      className="absolute left-0 top-0 block size-4 rounded-full bg-ink-dim"
      title="offline"
      data-chrome="offline"
    />
  );
}

const levelClass = {
  info: "bg-key-top text-ink border border-white/10",
  warning: "bg-accent-400 text-field",
  urgent: "bg-brand-600 text-ink",
} as const;

export function AnnouncementBar({ announcement }: { announcement: Announcement }) {
  const hu = pick(announcement.text, "hu");
  const en = announcement.text.en !== hu ? pick(announcement.text, "en") : "";
  return (
    <div
      className={`absolute bottom-[12px] left-0 flex h-[80px] w-full items-center rounded-[16px] px-8 ${levelClass[announcement.level]}`}
      data-chrome="announcement"
      role="status"
    >
      <div className="flex min-w-0 flex-col leading-tight">
        <span className="truncate text-[34px] font-semibold">{hu}</span>
        {en ? <span className="truncate text-[26px] opacity-80">{en}</span> : null}
      </div>
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
      className={`surface flex h-full w-full flex-col justify-center gap-6 border-l-[12px] px-16 ${border} ${tint}`}
      data-chrome="takeover"
      role="alert"
    >
      <p className="clamp-2 text-[72px] font-extrabold leading-[1.1]">{hu}</p>
      {en ? (
        <p className="clamp-2 text-[52px] font-semibold leading-[1.15] text-ink-muted">{en}</p>
      ) : null}
    </section>
  );
}
