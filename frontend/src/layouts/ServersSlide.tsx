import type { Pass } from "../api/client";
import { asLive, type ServersLive } from "../api/live";
import { UI, primaryLang } from "../lib/i18n";
import { EmptyState, Footer, Title } from "./common";

const MAX_CARDS = 8;

export function ServersSlide({ pass }: { pass: Pass }) {
  const live = asLive<ServersLive>(pass.live);
  const lang = primaryLang(pass.lang);
  const servers = live?.servers ?? [];
  const more = Math.max(servers.length - MAX_CARDS, 0);
  return (
    <div className="flex h-full flex-col gap-5">
      <div className="pr-[280px]">
        <Title pass={pass} size={72} />
      </div>
      {servers.length === 0 ? (
        <EmptyState pass={pass} />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-4 grid-rows-2 gap-6">
          {servers.slice(0, MAX_CARDS).map((server) => (
            <div key={`${server.game_slug}:${server.name}`} className="surface flex min-h-0 flex-col overflow-hidden p-0">
              <div
                className="flex h-[64px] items-center px-5 text-[30px] font-bold leading-none"
                style={{ background: server.color_bg, color: server.color_text }}
              >
                <span className="truncate">{server.game_short}</span>
              </div>
              <div className="flex min-h-0 flex-1 flex-col justify-between p-5">
                <span className="clamp-2 text-[34px] font-semibold leading-tight">{server.name}</span>
                <span className="self-end font-mono text-[40px] font-bold leading-none tabular">
                  {server.players_text}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-6">
        <Footer pass={pass} stale={Boolean(live?.stale)} />
        {more > 0 ? <span className="text-[30px] text-ink-muted">{UI[lang].more(more)}</span> : null}
      </div>
    </div>
  );
}
