import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router";
import { useInterval } from "usehooks-ts";

import { ApiError, fetchBundle, isSettled, makeClient, type Pass, type PassLang } from "./api/client";
import { AnnouncementBar, OfflineNote, Takeover, TopRight } from "./components/Chrome";
import { Rotation } from "./components/Rotation";
import { Stage } from "./components/Stage";
import { announcementDisplay } from "./lib/announcements";
import { serverNow } from "./lib/clock";
import { UI } from "./lib/i18n";
import { useFreshPage } from "./lib/reload";

const OFFLINE_AFTER_MS = 60_000;
// Without the server for this long, what the live slides say can no longer be true: the
// schedule's "now", the match being played. They leave the rotation until it is back.
const LIVE_DATA_EXPIRES_AFTER_MS = 5 * 60_000;
const BAR_SPACE = 104;

/** Two lines in the middle of the screen for the states that have no slides to show. */
function Notice({ hu, en, detail }: { hu: string; en: string; detail?: string }) {
  return (
    <div
      className="flex h-full w-full flex-col justify-end gap-1 pb-6 text-[30px] text-ink-dim"
      data-testid="empty"
    >
      <span>
        {hu}
        {detail ? `: ${detail}` : ""}
      </span>
      <span className="text-[0.72em]">{en}</span>
    </div>
  );
}

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
    // An answer that will not change is not asked for again at once. The interval above
    // still asks, so a screen that is enabled later comes up by itself.
    retry: (failures, error) => !isSettled(error) && failures < 3,
  });

  // Re-render now and then for what depends on the time alone: going offline, an
  // announcement reaching its end.
  useInterval(() => setTick((n) => n + 1), 5_000);
  useFreshPage(!preview);

  const onPassChange = useCallback((pass: Pass) => setCurrentLang(pass.lang), []);

  const bundle = query.data;
  const refused = query.error instanceof ApiError ? query.error.status : null;
  const sinceUpdate = Date.now() - query.dataUpdatedAt;
  const unavailable = query.failureCount > 0 || query.fetchStatus === "paused";
  const offline = unavailable && sinceUpdate > OFFLINE_AFTER_MS;
  const liveDataExpired = unavailable && sinceUpdate > LIVE_DATA_EXPIRES_AFTER_MS;

  // An announcement leaves the screen when it ends, not when the next answer says so.
  const announcements = (bundle?.announcements ?? []).filter(
    (announcement) => !announcement.ends_at || Date.parse(announcement.ends_at) > serverNow(),
  );
  const { takeover, bars } = announcementDisplay(announcements);
  const allPasses = bundle?.passes;
  const passes = useMemo(
    () =>
      // The countdown runs on the clock, which the screen keeps by itself.
      (allPasses ?? []).filter(
        (pass) =>
          !liveDataExpired || !pass.source.startsWith("live:") || pass.source === "live:clock",
      ),
    [allPasses, liveDataExpired],
  );
  const backgroundUrl = bundle?.stage.background_url ?? `${apiBase}display/background.svg`;
  const nothing = bundle ? <Notice hu={UI.hu.nothing} en={UI.en.nothing} /> : null;

  let content;
  if (refused === 404) {
    // The address names a screen the admin does not have, or has turned off.
    content = <Notice hu={UI.hu.unknownScreen} en={UI.en.unknownScreen} detail={screen} />;
  } else if (refused === 403 && preview) {
    content = <Notice hu={UI.hu.previewNeedsLogin} en={UI.en.previewNeedsLogin} />;
  } else if (takeover) {
    content = <Takeover announcement={takeover} />;
  } else {
    content = (
      <Rotation
        passes={passes}
        showProgress={Boolean(bundle?.screen.show_progress) && !preview}
        frozen={Boolean(preview) && passes.length <= 1}
        empty={nothing}
        onPassChange={onPassChange}
      />
    );
  }

  return (
    <Stage backgroundUrl={backgroundUrl} stage={bundle?.stage}>
      <OfflineNote visible={offline && refused === null} />
      {bundle ? (
        <TopRight
          showClock={bundle.screen.show_clock}
          timeZone={bundle.clock.timezone}
          lang={takeover ? "both" : currentLang}
        />
      ) : null}
      <div
        className="absolute left-0 top-0 w-full"
        style={{ bottom: bars.length > 0 ? BAR_SPACE : 0 }}
        data-rotation-area
      >
        {content}
      </div>
      {bars.length > 0 ? <AnnouncementBar key={bars[0]?.level} announcements={bars} /> : null}
    </Stage>
  );
}
