import createClient from "openapi-fetch";

import { syncClock } from "../lib/clock";
import type { components, paths } from "./schema";

export type Bundle = components["schemas"]["Bundle"];
export type Pass = components["schemas"]["Pass"];
export type SlideContent = components["schemas"]["SlideContent"];
export type SlideItem = components["schemas"]["SlideItem"];
export type Announcement = components["schemas"]["Announcement"];
export type Bilingual = components["schemas"]["Bilingual"];
export type ScheduleEntryView = components["schemas"]["ScheduleEntryView"];
export type ScreenListItem = components["schemas"]["ScreenListItem"];
export type Lang = "hu" | "en";
export type PassLang = Lang | "both";

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

/** Whether asking again could help. A screen that does not exist, or a preview without a
    login, gets the same answer every time. */
export function isSettled(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404);
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
): Promise<Bundle> {
  const query: Record<string, string> = {};
  if (params.preview) query.preview = params.preview;
  if (params.lang) query.lang = params.lang;
  if (params.phase) query.phase = params.phase;
  const result = await client.GET("/api/v1/screens/{slug}/bundle/", {
    params: { path: { slug }, query },
    cache: "no-store",
  });
  if (!result.data) {
    throw new ApiError(result.response.status, "bundle request");
  }
  syncClock(result.data.clock.now);
  return result.data;
}

export async function fetchScreens(client: ApiClient): Promise<ScreenListItem[]> {
  const result = await client.GET("/api/v1/screens/", { cache: "no-store" });
  if (!result.data) {
    throw new ApiError(result.response.status, "screen list request");
  }
  return result.data;
}
