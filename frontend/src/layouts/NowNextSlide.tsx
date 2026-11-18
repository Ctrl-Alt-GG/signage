import type { LiveSchedulePass, PassLang, ScheduleEntryView } from "../api/client";
import { UI, joined, pick, uiMore } from "../lib/i18n";
import { Card, EmptyState, Footer, SectionLabel, Title, typeAccent } from "./common";

// What fits in one column: two entries, or one and the count of the others, as on the
// servers and streams slides.
const MAX_ENTRIES = 2;

function visible(entries: ScheduleEntryView[]): ScheduleEntryView[] {
  return entries.length > MAX_ENTRIES ? entries.slice(0, MAX_ENTRIES - 1) : entries;
}

/** One schedule entry inside a now/next card: its time and headline, and one line beneath.
    The game name is the headline when there is one, with the slot title beneath; breaks and
    highlights without a game promote the title, with its English and the note beneath. Two
    entries fit in a card under a title in both languages. */
function EntryBlock({ entry, lang }: { entry: ScheduleEntryView; lang: PassLang }) {
  const headline = entry.game?.name || pick(entry.title, lang === "en" ? "en" : "hu");
  const english = !entry.game && lang === "both" && entry.title.en !== entry.title.hu ? entry.title.en : "";
  const sub = entry.game
    ? joined(entry.title, lang)
    : [english, joined(entry.note, lang)].filter(Boolean).join(" · ");
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <div className="flex min-w-0 items-baseline gap-4">
        <span
          className="shrink-0 font-mono text-[30px] font-bold leading-none tabular"
          style={{ color: typeAccent(entry.type) }}
        >
          {entry.time}
        </span>
        <span className="min-w-0 truncate text-[36px] font-extrabold leading-[1.15] tracking-[-0.01em]" data-allow-clip>
          {headline}
        </span>
      </div>
      {sub ? (
        <span className="truncate text-[24px] leading-tight text-ink-muted" data-allow-clip>
          {sub}
        </span>
      ) : null}
    </div>
  );
}

export function NowNextSlide({ pass }: { pass: LiveSchedulePass }) {
  const live = pass.live;
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
              className="gap-3 overflow-hidden"
            >
              <SectionLabel>{label}</SectionLabel>
              {entries.length === 0 ? (
                <span className="text-[30px] text-ink-dim">-</span>
              ) : (
                visible(entries).map((entry) => (
                  <EntryBlock key={entry.starts_at + entry.title.hu} entry={entry} lang={pass.lang} />
                ))
              )}
              {entries.length > visible(entries).length ? (
                <span className="text-[28px] font-semibold leading-tight text-ink-muted">
                  {uiMore(entries.length - visible(entries).length, pass.lang, "moreEntries")}
                </span>
              ) : null}
            </Card>
          ))}
        </div>
      )}
      <Footer pass={pass} />
    </div>
  );
}
