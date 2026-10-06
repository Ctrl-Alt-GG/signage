import type { Pass, ScheduleEntryView } from "../api/client";
import { asLive, type ScheduleLive } from "../api/live";
import { UI, pick, primaryLang } from "../lib/i18n";
import { Card, EmptyState, Footer, SectionLabel, Title, typeAccent } from "./common";

function EntryBlock({ entry, lang }: { entry: ScheduleEntryView; lang: "hu" | "en" }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="font-mono text-[44px] font-bold leading-none tabular" style={{ color: typeAccent(entry.type) }}>
        {entry.time}
      </span>
      <span className="clamp-2 text-[36px] font-semibold leading-tight">{pick(entry.title, lang)}</span>
      {entry.label ? (
        <span className="badge badge-outline h-[40px] w-fit border-ink-dim px-4 text-[26px] font-semibold">
          {entry.label}
        </span>
      ) : null}
      {pick(entry.note, lang) ? (
        <span className="clamp-2 text-[26px] leading-tight text-ink-muted">{pick(entry.note, lang)}</span>
      ) : null}
    </div>
  );
}

export function NowNextSlide({ pass }: { pass: Pass }) {
  const live = asLive<ScheduleLive>(pass.live);
  const lang = primaryLang(pass.lang);
  const labels = pass.content.labels;
  const columns: Array<[string, ScheduleEntryView[]]> = [
    [pick(labels.now, lang) || UI[lang].now, live?.now ?? []],
    [pick(labels.next, lang) || UI[lang].next, live?.next ?? []],
    [pick(labels.later, lang) || UI[lang].later, live?.later ?? []],
  ];
  const empty = !live || columns.every(([, entries]) => entries.length === 0);
  return (
    <div className="flex h-full flex-col gap-6">
      <div className="pr-[280px]">
        <Title pass={pass} size={72} />
      </div>
      {empty ? (
        <EmptyState pass={pass} />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-3 gap-8">
          {columns.map(([label, entries]) => (
            <Card key={label} accent={entries[0] ? typeAccent(entries[0].type) : "#7a4d4d"} className="gap-4">
              <SectionLabel>{label}</SectionLabel>
              {entries.length === 0 ? (
                <span className="text-[30px] text-ink-dim">-</span>
              ) : (
                entries.map((entry) => <EntryBlock key={entry.starts_at + entry.title.hu} entry={entry} lang={lang} />)
              )}
            </Card>
          ))}
        </div>
      )}
      <Footer pass={pass} />
    </div>
  );
}
