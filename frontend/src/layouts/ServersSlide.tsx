import type { LiveProjectilePass } from "../api/client";
import { uiMore } from "../lib/i18n";
import { EmptyState, Footer, Title } from "./common";

const MAX_CARDS = 8;

export function ServersSlide({ pass }: { pass: LiveProjectilePass }) {
  const live = pass.live;
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
          {servers.slice(0, MAX_CARDS).map((server, index) => (
            // Two servers can share a game and a name, so their place in the list is the key.
            <div key={index} className="surface flex min-h-0 flex-col overflow-hidden p-0">
              <div
                className="flex h-[52px] shrink-0 items-center justify-between gap-3 px-5 font-bold leading-none"
                style={{ background: server.color_bg, color: server.color_text }}
              >
                <span className="min-w-0 truncate text-[28px]" data-allow-clip>{server.game_short}</span>
                <span className="shrink-0 font-mono text-[32px] tabular">{server.players_text}</span>
              </div>
              <div className="flex min-h-0 flex-1 items-center px-5">
                <span className="min-w-0 truncate text-[30px] font-semibold leading-tight" data-allow-clip>{server.name}</span>
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-6">
        <Footer pass={pass} stale={Boolean(live?.stale)} />
        {more > 0 ? <span className="text-[30px] text-ink-muted">{uiMore(more, pass.lang)}</span> : null}
      </div>
    </div>
  );
}
