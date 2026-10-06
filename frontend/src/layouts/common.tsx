import { DynamicIcon, type IconName } from "lucide-react/dynamic";
import type { ReactNode } from "react";

import type { Pass, PassLang, SlideItem } from "../api/client";
import { Markdown } from "../components/Markdown";
import { Text, UI, joined, pick, primaryLang } from "../lib/i18n";

export function Kicker({ pass }: { pass: Pass }) {
  const text = joined(pass.content.kicker, pass.lang);
  if (!text) return null;
  return (
    <p className="text-[30px] font-semibold uppercase leading-tight tracking-[0.12em] text-ink-muted">
      {text}
    </p>
  );
}

export function Title({ pass, size = 72 }: { pass: Pass; size?: number }) {
  return (
    <div style={{ fontSize: size }} className="max-w-[1400px]">
      <Text
        text={pass.content.title}
        lang={pass.lang}
        as="h1"
        className="font-extrabold leading-[1.1] tracking-[-0.02em] [text-wrap:balance]"
        secondaryClassName="text-[0.7em] font-semibold"
      />
    </div>
  );
}

export function Body({ pass, size = 44 }: { pass: Pass; size?: number }) {
  const body = pass.content.body;
  if (!body) return null;
  if (pass.lang !== "both") {
    const value = pick(body, pass.lang);
    return value ? (
      <p className="clamp-3 max-w-[1400px] font-medium leading-[1.3]" style={{ fontSize: size }}>
        <Markdown text={value} />
      </p>
    ) : null;
  }
  const hu = pick(body, "hu");
  const en = body.en && body.en !== body.hu ? body.en : "";
  return (
    <div className="max-w-[1400px] space-y-2">
      {hu ? (
        <p className="clamp-3 font-medium leading-[1.3]" style={{ fontSize: size }}>
          <Markdown text={hu} />
        </p>
      ) : null}
      {en ? (
        <p className="clamp-2 font-medium leading-[1.3] text-ink-muted" style={{ fontSize: size * 0.7 }}>
          <Markdown text={en} />
        </p>
      ) : null}
    </div>
  );
}

export function Footer({ pass, stale = false }: { pass: Pass; stale?: boolean }) {
  const lang = primaryLang(pass.lang);
  const text = joined(pass.content.footer, pass.lang);
  if (!text && !stale) return null;
  return (
    <p className="mt-auto flex items-center gap-4 text-[28px] font-medium leading-tight text-ink-muted">
      {text ? <Markdown text={text} /> : null}
      {stale ? (
        <span className="badge badge-outline h-[36px] border-ink-dim px-3 text-[22px] text-ink-dim">
          {UI[lang].stale}
        </span>
      ) : null}
    </p>
  );
}

export function ItemIcon({ name, index, size = 36 }: { name?: string; index: number; size?: number }) {
  return (
    <span
      className="flex w-[48px] shrink-0 justify-center font-mono font-bold leading-none text-brand-500 tabular"
      style={{ fontSize: size, paddingTop: size * 0.15 }}
    >
      {name ? (
        <DynamicIcon name={name as IconName} size={size} strokeWidth={2.5} aria-hidden fallback={() => <>{index + 1}</>} />
      ) : (
        index + 1
      )}
    </span>
  );
}

/** Pick a font size so the estimated line count fits the available height. Lines are
    estimated from the text length and the column width at the candidate size; English
    lines (when stacked) are counted at the secondary scale. */
const EN_SCALE = 0.72;
const LINE = 1.3;

function estimateLines(text: string, size: number, columnWidth: number): number {
  if (!text) return 0;
  const charsPerLine = Math.max(10, Math.floor(columnWidth / (size * 0.52)));
  return Math.ceil(text.length / charsPerLine);
}

export function fitItemSize(
  items: SlideItem[],
  lang: PassLang,
  availableHeight: number,
  columnWidth: number,
  max = 40,
  min = 26,
): number {
  for (let size = max; size >= min; size -= 2) {
    let height = 0;
    for (const item of items) {
      if (lang === "both") {
        height += estimateLines(item.hu, size, columnWidth) * size * LINE;
        if (item.en && item.en !== item.hu) {
          height += estimateLines(item.en, size * EN_SCALE, columnWidth) * size * EN_SCALE * LINE;
        }
      } else {
        height += estimateLines(pick(item, lang), size, columnWidth) * size * LINE;
      }
    }
    height += 0.45 * size * Math.max(items.length - 1, 0);
    if (height <= availableHeight) return size;
  }
  return min;
}

export function Items({
  items,
  lang,
  size = 40,
  availableHeight = 470,
  columnWidth = 1000,
  className = "",
}: {
  items: SlideItem[];
  lang: PassLang;
  size?: number;
  availableHeight?: number;
  columnWidth?: number;
  className?: string;
}) {
  const shown = items.slice(0, 6);
  const fitted = fitItemSize(shown, lang, availableHeight, columnWidth, size);
  return (
    <ol className={`flex h-full flex-col justify-evenly ${className}`} style={{ gap: fitted * 0.25 }}>
      {shown.map((item, index) => (
        <li key={index} className="flex items-start gap-4 leading-[1.3]" style={{ fontSize: fitted }}>
          <ItemIcon name={item.icon} index={index} size={fitted * 0.9} />
          <span className="min-w-0 font-medium">
            {lang === "both" ? (
              <>
                <span className="block">
                  <Markdown text={item.hu} />
                </span>
                {item.en && item.en !== item.hu ? (
                  <span className="block text-[0.72em] text-ink-muted">
                    <Markdown text={item.en} />
                  </span>
                ) : null}
              </>
            ) : (
              <span className="block">
                <Markdown text={pick(item, lang)} />
              </span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function EmptyState({ pass }: { pass: Pass }) {
  const empty = pass.content.empty;
  const hu = pick(empty, "hu") || UI.hu.nothing;
  const en = empty?.en && empty.en !== empty.hu ? empty.en : UI.en.nothing;
  if (pass.lang === "en") {
    return (
      <div className="flex flex-1 items-center text-ink-muted">
        <p className="text-[44px] font-medium">{pick(empty, "en") || UI.en.nothing}</p>
      </div>
    );
  }
  return (
    <div className="flex flex-1 flex-col justify-center gap-2 text-ink-muted">
      <p className="text-[44px] font-medium">{hu}</p>
      {pass.lang === "both" ? <p className="text-[32px]">{en}</p> : null}
    </div>
  );
}

export function Card({
  children,
  className = "",
  accent,
}: {
  children: ReactNode;
  className?: string;
  accent?: string;
}) {
  return (
    <div
      className={`surface flex flex-col p-6 ${className}`}
      style={accent ? { borderLeft: `6px solid ${accent}` } : undefined}
    >
      {children}
    </div>
  );
}

export function typeAccent(type: string): string {
  if (type === "break") return "#e8b923";
  if (type === "highlight") return "#aa0000";
  return "rgba(170, 0, 0, 0.6)";
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-[26px] font-semibold uppercase leading-none tracking-[0.12em] text-ink-muted">
      {children}
    </p>
  );
}
