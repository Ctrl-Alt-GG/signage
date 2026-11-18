import createClient from "openapi-fetch";

import { syncClock } from "../lib/clock";
import type { components, paths } from "./schema";

type Schemas = components["schemas"];

export type Bundle = Schemas["Bundle"];
/** A slide in one language. Its source says what its live data is and which layouts can
    draw it, as src/signage/content/lint.py pairs them. */
export type Pass = Schemas["Pass"];
export type PassOf<S extends Pass["source"]> = Extract<Pass, { source: S }>;
export type StaticPass = PassOf<"static">;
export type LiveClockPass = PassOf<"live:clock">;
export type LiveSchedulePass = PassOf<"live:schedule">;
export type LiveProjectilePass = PassOf<"live:projectile">;
export type LiveBracketPass = PassOf<"live:bracket">;
export type LiveStreamsPass = PassOf<"live:streams">;
export type MatchRow = Schemas["MatchRow"];
export type ServersLive = Schemas["ServersLive"];
export type StreamsLive = Schemas["StreamsLive"];
export type SlideContent = Schemas["SlideContent"];
export type SlideItem = Schemas["SlideItem"];
export type Announcement = Schemas["Announcement"];
export type Bilingual = Schemas["Bilingual"];
export type ScheduleEntryView = Schemas["ScheduleEntryView"];
export type ScreenListItem = Schemas["ScreenListItem"];
export type Lang = "hu" | "en";
export type PassLang = Lang | "both";

// The server gives up on the upstream systems of a bundle after 15 seconds by default
// (SIGNAGE_BUNDLE_UPSTREAM_SECONDS), so an answer that has not come in twice that time is
// not coming. A request without a limit could wait for good, and the screen would not ask
// again while it does.
const REQUEST_TIMEOUT_MS = 30_000;

/** Ends a request when `signal` says so, or when it has taken too long. */
function bounded(signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}

export function makeClient(baseUrl: string) {
  return createClient<paths>({ baseUrl });
}

export type ApiClient = ReturnType<typeof makeClient>;

/** An answer the server gave on purpose, as opposed to no answer at all. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    what: string,
  ) {
    super(`${what} failed with ${status}`);
  }
}

/** Whether asking again could help. A screen that does not exist or is turned off, or a
    preview without a login, gets the same answer every time. */
export function isSettled(error: unknown): boolean {
  return error instanceof ApiError && [403, 404, 410].includes(error.status);
}

export interface BundleParams {
  preview?: string;
  lang?: string;
  phase?: string;
}

export async function fetchBundle(
  client: ApiClient,
  slug: string,
  params: BundleParams,
  signal?: AbortSignal,
): Promise<Bundle> {
  const query: Record<string, string> = {};
  if (params.preview) query.preview = params.preview;
  if (params.lang) query.lang = params.lang;
  if (params.phase) query.phase = params.phase;
  const result = await client.GET("/api/v1/screens/{slug}/bundle/", {
    params: { path: { slug }, query },
    cache: "no-store",
    signal: bounded(signal),
  });
  if (!result.data) {
    throw new ApiError(result.response.status, "bundle request");
  }
  syncClock(result.data.clock.now);
  return result.data;
}

export async function fetchScreens(client: ApiClient, signal?: AbortSignal): Promise<ScreenListItem[]> {
  const result = await client.GET("/api/v1/screens/", { cache: "no-store", signal: bounded(signal) });
  if (!result.data) {
    throw new ApiError(result.response.status, "screen list request");
  }
  return result.data;
}
