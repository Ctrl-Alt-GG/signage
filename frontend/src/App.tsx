import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router";
import { useInterval } from "usehooks-ts";

import { fetchBundle, makeClient, type Pass, type PassLang } from "./api/client";
import { AnnouncementBar, OfflineDot, Takeover, TopRight } from "./components/Chrome";
import { Rotation } from "./components/Rotation";
import { Stage } from "./components/Stage";
import { UI } from "./lib/i18n";

const OFFLINE_AFTER_MS = 60_000;
const RELOAD_AFTER_MS = 6 * 60 * 60 * 1000;
const BAR_SPACE = 104;

export function App({ apiBase, fallbackScreen = "main" }: { apiBase: string; fallbackScreen?: string }) {
  const { slug } = useParams();
  const [search] = useSearchParams();
  const screen = slug ?? fallbackScreen;
  const preview = search.get("preview") ?? undefined;
  const previewLang = search.get("lang") ?? undefined;
  const phase = search.get("phase") ?? undefined;
  const client = useMemo(() => makeClient(window.location.origin), []);
  const [currentLang, setCurrentLang] = useState<PassLang>("hu");
  const [, setTick] = useState(0);

  const query = useQuery({
    queryKey: ["bundle", screen, preview ?? "", previewLang ?? "", phase ?? ""],
    queryFn: () => fetchBundle(client, screen, { preview, lang: previewLang, phase }),
    refetchInterval: (q) => (q.state.data?.screen.refresh_seconds ?? 20) * 1000,
    refetchIntervalInBackground: true,
    placeholderData: (previous) => previous,
  });

  useInterval(() => setTick((n) => n + 1), 5_000);
  useInterval(() => {
    if (!query.isError && !preview) window.location.reload();
  }, RELOAD_AFTER_MS);

  const onPassChange = useCallback((pass: Pass) => setCurrentLang(pass.lang), []);

  const bundle = query.data;
  const offline = query.failureCount > 0 && Date.now() - query.dataUpdatedAt > OFFLINE_AFTER_MS;
  const announcement = bundle?.announcement ?? null;
  const takeover = Boolean(announcement?.takeover);
  const passes = bundle?.passes ?? [];
  const backgroundUrl = `${apiBase}display/background.svg`;

  return (
    <Stage backgroundUrl={backgroundUrl}>
      <OfflineDot visible={offline} />
      {bundle ? (
        <TopRight
          showClock={bundle.screen.show_clock}
          timeZone={bundle.clock.timezone}
          lang={takeover ? "both" : currentLang}
        />
      ) : null}
      <div
        className="absolute left-0 top-0 w-full"
        style={{ bottom: announcement && !takeover ? BAR_SPACE : 0 }}
        data-rotation-area
      >
        {takeover && announcement ? (
          <Takeover announcement={announcement} />
        ) : passes.length > 0 ? (
          <Rotation
            passes={passes}
            showProgress={Boolean(bundle?.screen.show_progress) && !preview}
            frozen={Boolean(preview)}
            onPassChange={onPassChange}
          />
        ) : (
          <div className="flex h-full w-full items-end pb-6 text-[30px] text-ink-dim" data-testid="empty">
            {bundle ? UI.hu.nothing : ""}
          </div>
        )}
      </div>
      {announcement && !takeover ? <AnnouncementBar announcement={announcement} /> : null}
    </Stage>
  );
}
