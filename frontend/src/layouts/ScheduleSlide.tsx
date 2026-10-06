import type { Pass } from "../api/client";
import { asLive, type ScheduleLive } from "../api/live";
import { pick, primaryLang } from "../lib/i18n";
import { EmptyState, Footer, Title, typeAccent } from "./common";

export function ScheduleSlide({ pass }: { pass: Pass }) {
  const live = asLive<ScheduleLive>(pass.live);
  const lang = primaryLang(pass.lang);
  const rows = live?.upcoming ?? [];
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="pr-[280px]">
        <Title pass={pass} size={72} />
      </div>
      {rows.length === 0 ? (
        <EmptyState pass={pass} />
      ) : (
        <ol className="flex min-h-0 flex-1 flex-col justify-evenly pb-4">
          {rows.slice(0, 8).map((entry, index) => {
            const accent = typeAccent(entry.type);
            return (
              <li key={entry.starts_at + entry.title.hu} className="flex items-center gap-6 leading-tight">
                <span className="w-[140px] shrink-0 font-mono text-[36px] font-bold tabular" style={{ color: accent }}>
                  {entry.time}
                </span>
                <span
                  className="relative flex w-[24px] shrink-0 items-center justify-center"
                  aria-hidden
                >
                  <span className="block size-[14px] rounded-full" style={{ background: accent }} />
                  {index < Math.min(rows.length, 8) - 1 ? (
                    <span className="absolute left-1/2 top-[14px] h-[60px] w-[2px] -translate-x-1/2 bg-ink-dim/50" />
                  ) : null}
                </span>
                <span className="min-w-0 flex-1 truncate text-[36px] font-semibold">{pick(entry.title, lang)}</span>
                {entry.label ? (
                  <span className="badge badge-outline h-[38px] shrink-0 border-ink-dim px-4 text-[24px] font-semibold">
                    {entry.label}
                  </span>
                ) : null}
                {pick(entry.note, lang) ? (
                  <span className="max-w-[520px] shrink-0 truncate text-[26px] text-ink-muted">
                    {pick(entry.note, lang)}
                  </span>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
      <Footer pass={pass} />
    </div>
  );
}
