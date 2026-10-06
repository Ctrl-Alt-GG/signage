import type { Pass, ScheduleEntryView } from "../api/client";
import { asLive, type ScheduleLive } from "../api/live";
import { UI, joined, pick } from "../lib/i18n";
import { Card, EmptyState, Footer, SectionLabel, Title, typeAccent } from "./common";

/** One schedule entry inside a now/next card: the game name is the headline when there is
    one, the slot title is the small line beneath; breaks and highlights without a game
    promote the title and show the note instead. */
function EntryBlock({ entry, lang }: { entry: ScheduleEntryView; lang: Pass["lang"] }) {
  const headline = entry.game?.name || pick(entry.title, lang === "en" ? "en" : "hu");
  const sub = entry.game ? joined(entry.title, lang) : joined(entry.note, lang);
  return (
    <div className="flex flex-col gap-2">
      <span
        className="font-mono text-[40px] font-bold leading-none tabular"
        style={{ color: typeAccent(entry.type) }}
      >
        {entry.time}
      </span>
      <span className="text-[44px] font-extrabold leading-[1.1] tracking-[-0.01em]">{headline}</span>
      {!entry.game && lang === "both" && entry.title.en && entry.title.en !== entry.title.hu ? (
        <span className="text-[30px] font-semibold leading-tight text-ink-muted">{entry.title.en}</span>
      ) : null}
      {sub ? <span className="text-[26px] leading-tight text-ink-muted">{sub}</span> : null}
    </div>
  );
}

export function NowNextSlide({ pass }: { pass: Pass }) {
  const live = asLive<ScheduleLive>(pass.live);
  const labels = pass.content.labels;
  const fallback = { now: UI.hu.now + " · " + UI.en.now, next: UI.hu.next + " · " + UI.en.next, later: UI.hu.later + " · " + UI.en.later };
  const columns: Array<[string, ScheduleEntryView[]]> = [
    [joined(labels.now, pass.lang) || fallback.now, live?.now ?? []],
    [joined(labels.next, pass.lang) || fallback.next, live?.next ?? []],
    [joined(labels.later, pass.lang) || fallback.later, live?.later ?? []],
  ];
  const empty = !live || columns.every(([, entries]) => entries.length === 0);
  return (
    <div className="flex h-full flex-col gap-5">
      <div className="pr-[280px]">
        <Title pass={pass} size={56} />
      </div>
      {empty ? (
        <EmptyState pass={pass} />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-3 gap-8">
          {columns.map(([label, entries]) => (
            <Card
              key={label}
              accent={entries[0] ? typeAccent(entries[0].type) : "#7a4d4d"}
              className="gap-4 overflow-hidden"
            >
              <SectionLabel>{label}</SectionLabel>
              {entries.length === 0 ? (
                <span className="text-[30px] text-ink-dim">-</span>
              ) : (
                entries.slice(0, 2).map((entry) => (
                  <EntryBlock key={entry.starts_at + entry.title.hu} entry={entry} lang={pass.lang} />
                ))
              )}
            </Card>
          ))}
        </div>
      )}
      <Footer pass={pass} />
    </div>
  );
}
