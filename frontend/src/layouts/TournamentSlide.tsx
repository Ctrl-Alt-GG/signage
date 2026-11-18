import type { LiveBracketPass, MatchRow } from "../api/client";
import { joined, pick, primaryLang, ui } from "../lib/i18n";
import { Card, EmptyState, Footer, SectionLabel, Title } from "./common";

function Teams({ match, size }: { match: MatchRow; size: number }) {
  return (
    <div className="flex items-center justify-between gap-4 leading-tight" style={{ fontSize: size }}>
      <span className="min-w-0 flex-1 truncate font-semibold" data-allow-clip>{match.team1}</span>
      <span className="shrink-0 text-ink-muted">vs</span>
      <span className="min-w-0 flex-1 truncate text-right font-semibold" data-allow-clip>{match.team2}</span>
    </div>
  );
}

export function TournamentSlide({ pass }: { pass: LiveBracketPass }) {
  const live = pass.live;
  const lang = primaryLang(pass.lang);
  const labels = pass.content.labels;
  const liveMatches = live?.live ?? [];
  const page = live?.live_page;
  const upcoming = live?.upcoming ?? [];
  const results = live?.results ?? [];
  const nothing = liveMatches.length + upcoming.length + results.length === 0;
  return (
    <div className="flex h-full flex-col gap-5">
      <div className="flex items-baseline gap-6 pr-[280px]">
        <Title pass={pass} size={72} />
        {live?.name ? <span className="truncate text-[36px] text-ink-muted" data-allow-clip>{live.name}</span> : null}
      </div>
      {nothing ? (
        <EmptyState pass={pass} />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,0.9fr)] gap-6">
          <Card className="gap-3" accent="#aa0000">
            <div className="flex items-center justify-between gap-3">
              <SectionLabel>{joined(labels.live, pass.lang)}</SectionLabel>
              {page && page.count > 1 ? (
                <span className="shrink-0 font-mono text-[24px] text-ink-muted" aria-label={ui("liveMatchPages", pass.lang)}>
                  {page.first}-{page.last} / {page.total}
                </span>
              ) : null}
            </div>
            {liveMatches.length === 0 ? (
              <span className="text-[30px] text-ink-dim">{pick(pass.content.empty, lang)}</span>
            ) : (
              liveMatches.map((match) => (
                <div key={match.id ?? match.team1 + match.team2} className="flex flex-col gap-1">
                  <Teams match={match} size={30} />
                  <span className="flex items-center gap-3 text-[22px] leading-tight text-ink-muted">
                    {/* The dot is for a match in its planned time. One that ran past it
                        has started and has no result yet, which is all that is known, so
                        that comes first where the dot would be. */}
                    {match.status === "awaiting" ? null : (
                      <span className="block size-4 shrink-0 animate-pulse-dot rounded-full bg-brand-500" />
                    )}
                    <span className="min-w-0 truncate" data-allow-clip>
                      {match.status === "awaiting" ? `${ui("awaiting", pass.lang)} · ` : ""}
                      {match.round} {match.start_local}
                    </span>
                  </span>
                </div>
              ))
            )}
          </Card>
          <Card className="gap-3">
            <SectionLabel>{joined(labels.upcoming, pass.lang)}</SectionLabel>
            {upcoming.length === 0 ? (
              <span className="text-[30px] text-ink-dim">-</span>
            ) : (
              <div className="flex flex-col gap-2">
                {upcoming.slice(0, 4).map((match) => (
                  <div key={match.id ?? match.team1 + match.team2} className="flex items-center gap-4 leading-tight">
                    <span className="w-[90px] shrink-0 font-mono text-[26px] font-bold tabular text-ink-muted">
                      {match.start_local}
                    </span>
                    <div className="min-w-0 flex-1">
                      <Teams match={match} size={26} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
          <Card className="gap-3">
            <SectionLabel>{joined(labels.results, pass.lang)}</SectionLabel>
            {results.length === 0 ? (
              <span className="text-[30px] text-ink-dim">-</span>
            ) : (
              results.slice(0, 3).map((match) => (
                <div key={match.id ?? match.team1 + match.team2} className="flex items-center gap-3 text-[28px] leading-tight">
                  <span className="min-w-0 flex-1 truncate font-semibold" data-allow-clip>{match.team1}</span>
                  <span className="shrink-0 font-mono text-[30px] font-bold tabular">
                    {match.score1} : {match.score2}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-right font-semibold" data-allow-clip>{match.team2}</span>
                </div>
              ))
            )}
          </Card>
        </div>
      )}
      <Footer pass={pass} stale={Boolean(live?.stale)} />
    </div>
  );
}
