import type { LiveStreamsPass } from "../api/client";
import { UI, ui, uiMore } from "../lib/i18n";
import { EmptyState, Footer, Title } from "./common";

const MAX_TILES = 4;

const UNAVAILABLE = { hu: UI.hu.streamsUnavailable, en: UI.en.streamsUnavailable };

export function StreamsSlide({ pass }: { pass: LiveStreamsPass }) {
  const live = pass.live;
  const channels = live?.live ?? [];
  // Streams can't tell which channels are live, and has no recent list to show instead.
  // The slide says so: "nothing is live" would not be known to be true.
  const unavailable = channels.length === 0 && (live?.source_status === "unavailable" || Boolean(live?.empty));
  const more = Math.max(channels.length - MAX_TILES, 0);
  return (
    <div className="flex h-full flex-col gap-5">
      <div className="pr-[280px]">
        <Title pass={pass} size={72} />
      </div>
      {channels.length === 0 ? (
        <EmptyState pass={pass} text={unavailable ? UNAVAILABLE : undefined} />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-4 gap-6">
          {channels.slice(0, MAX_TILES).map((channel) => (
            <div key={channel.id} className="surface flex min-h-0 flex-col overflow-hidden p-0">
              <div className="min-h-0 w-full flex-1 bg-key-top">
                {channel.thumbnail_url ? (
                  <img src={channel.thumbnail_url} alt="" className="size-full object-cover" loading="lazy" />
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-3 p-4">
                <span className="block size-4 animate-pulse-dot rounded-full bg-brand-500" aria-hidden />
                <span className="min-w-0 flex-1 truncate text-[32px] font-semibold leading-tight" data-allow-clip>{channel.name}</span>
                {channel.audio_only ? (
                  <span className="badge badge-outline h-[34px] border-ink-dim px-3 text-[22px] uppercase text-ink-muted">
                    {ui("audio", pass.lang)}
                  </span>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-6">
        {/* Channels from an earlier answer are marked as such; the notice says enough. */}
        <Footer pass={pass} stale={Boolean(live?.stale) && !unavailable} />
        {more > 0 ? (
          <span className="text-[30px] text-ink-muted">{uiMore(more, pass.lang, "moreStreams")}</span>
        ) : null}
      </div>
    </div>
  );
}
