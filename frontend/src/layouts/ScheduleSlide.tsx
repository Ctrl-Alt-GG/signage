import type { Pass } from "../api/client";
import { asLive, type ScheduleLive } from "../api/live";
import { joined, pick } from "../lib/i18n";
import { EmptyState, Footer, Title, typeAccent } from "./common";

const ROWS = 6;

/** A timeline of the current slot and the next five: time, game name large, slot title
    small. Notes are left out on purpose; the room reads this from metres away. */
export function ScheduleSlide({ pass }: { pass: Pass }) {
  const live = asLive<ScheduleLive>(pass.live);
  const rows = (live?.upcoming ?? []).slice(0, ROWS);
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="pr-[280px]">
        <Title pass={pass} size={56} />
      </div>
      {rows.length === 0 ? (
        <EmptyState pass={pass} />
      ) : (
        <ol className="flex min-h-0 flex-1 flex-col justify-evenly py-2">
          {rows.map((entry, index) => {
            const accent = typeAccent(entry.type);
            const headline = entry.game?.name || pick(entry.title, pass.lang === "en" ? "en" : "hu");
            const sub = entry.game
              ? joined(entry.title, pass.lang)
              : pass.lang === "both" && entry.title.en !== entry.title.hu
                ? entry.title.en
                : "";
            return (
              <li key={entry.starts_at + entry.title.hu} className="flex items-center gap-6 leading-tight">
                <span
                  className="w-[130px] shrink-0 font-mono text-[34px] font-bold tabular"
                  style={{ color: accent }}
                >
                  {entry.time}
                </span>
                <span className="relative flex w-[24px] shrink-0 items-center justify-center" aria-hidden>
                  <span className="block size-[14px] rounded-full" style={{ background: accent }} />
                  {index < rows.length - 1 ? (
                    <span className="absolute left-1/2 top-[14px] h-[52px] w-[2px] -translate-x-1/2 bg-ink-dim/50" />
                  ) : null}
                </span>
                <span className="flex min-w-0 flex-1 items-baseline gap-5">
                  <span className="shrink-0 text-[38px] font-extrabold tracking-[-0.01em]">{headline}</span>
                  {sub ? <span className="min-w-0 text-[26px] text-ink-muted">{sub}</span> : null}
                </span>
              </li>
            );
          })}
        </ol>
      )}
      <Footer pass={pass} />
    </div>
  );
}
