import type { Pass } from "../api/client";
import { asLive, type StreamsLive } from "../api/live";
import { ui } from "../lib/i18n";
import { EmptyState, Footer, Title } from "./common";

export function StreamsSlide({ pass }: { pass: Pass }) {
  const live = asLive<StreamsLive>(pass.live);
  const channels = live?.live ?? [];
  return (
    <div className="flex h-full flex-col gap-5">
      <div className="pr-[280px]">
        <Title pass={pass} size={72} />
      </div>
      {channels.length === 0 ? (
        <EmptyState pass={pass} />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-4 gap-6">
          {channels.slice(0, 4).map((channel) => (
            <div key={channel.id} className="surface flex min-h-0 flex-col overflow-hidden p-0">
              <div className="aspect-video w-full bg-key-top">
                {channel.thumbnail_url ? (
                  <img src={channel.thumbnail_url} alt="" className="size-full object-cover" loading="lazy" />
                ) : null}
              </div>
              <div className="flex items-center gap-3 p-4">
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
      <Footer pass={pass} stale={Boolean(live?.stale)} />
    </div>
  );
}
