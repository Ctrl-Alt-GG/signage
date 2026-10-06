import type { Pass } from "../api/client";
import { asLive, type MatchRow, type TournamentLive } from "../api/live";
import { pick, primaryLang } from "../lib/i18n";
import { Card, EmptyState, Footer, SectionLabel, Title } from "./common";

function Teams({ match, size }: { match: MatchRow; size: number }) {
  return (
    <div className="flex items-center justify-between gap-4 leading-tight" style={{ fontSize: size }}>
      <span className="min-w-0 flex-1 truncate font-semibold">{match.team1}</span>
      <span className="shrink-0 text-ink-muted">vs</span>
      <span className="min-w-0 flex-1 truncate text-right font-semibold">{match.team2}</span>
    </div>
  );
}

export function TournamentSlide({ pass }: { pass: Pass }) {
  const live = asLive<TournamentLive>(pass.live);
  const lang = primaryLang(pass.lang);
  const labels = pass.content.labels;
  const liveMatches = live?.live ?? [];
  const upcoming = live?.upcoming ?? [];
  const results = live?.results ?? [];
  const nothing = liveMatches.length + upcoming.length + results.length === 0;
  return (
    <div className="flex h-full flex-col gap-5">
      <div className="flex items-baseline gap-6 pr-[280px]">
        <Title pass={pass} size={72} />
        {live?.name ? <span className="truncate text-[36px] text-ink-muted">{live.name}</span> : null}
      </div>
      {nothing ? (
        <EmptyState pass={pass} />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[1.2fr_1fr_0.9fr] gap-6">
          <Card className="gap-4" accent="#aa0000">
            <SectionLabel>{pick(labels.live, lang)}</SectionLabel>
            {liveMatches.length === 0 ? (
              <span className="text-[30px] text-ink-dim">{pick(pass.content.empty, lang)}</span>
            ) : (
              liveMatches.slice(0, 2).map((match) => (
                <div key={match.id ?? match.team1 + match.team2} className="flex flex-col gap-2">
                  <Teams match={match} size={40} />
                  <span className="flex items-center gap-3 text-[26px] text-ink-muted">
                    <span className="block size-4 animate-pulse-dot rounded-full bg-brand-500" />
                    {match.round} {match.start_local}
                  </span>
                </div>
              ))
            )}
          </Card>
          <Card className="gap-3">
            <SectionLabel>{pick(labels.upcoming, lang)}</SectionLabel>
            {upcoming.length === 0 ? (
              <span className="text-[30px] text-ink-dim">-</span>
            ) : (
              upcoming.slice(0, 4).map((match) => (
                <div key={match.id ?? match.team1 + match.team2} className="flex items-center gap-4">
                  <span className="w-[110px] shrink-0 font-mono text-[32px] font-bold tabular text-ink-muted">
                    {match.start_local}
                  </span>
                  <div className="min-w-0 flex-1">
                    <Teams match={match} size={30} />
                  </div>
                </div>
              ))
            )}
          </Card>
          <Card className="gap-3">
            <SectionLabel>{pick(labels.results, lang)}</SectionLabel>
            {results.length === 0 ? (
              <span className="text-[30px] text-ink-dim">-</span>
            ) : (
              results.slice(0, 3).map((match) => (
                <div key={match.id ?? match.team1 + match.team2} className="flex items-center gap-3 text-[30px]">
                  <span className="min-w-0 flex-1 truncate font-semibold">{match.team1}</span>
                  <span className="shrink-0 font-mono text-[34px] font-bold tabular">
                    {match.score1} : {match.score2}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-right font-semibold">{match.team2}</span>
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
