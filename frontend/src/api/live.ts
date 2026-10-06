/* Shapes of the `live` field per layout. The backend serializes them as free-form JSON;
   these types mirror src/signage/rendering and src/signage/integrations. */

import type { ScheduleEntryView } from "./client";

export interface ScheduleLive {
  now: ScheduleEntryView[];
  next: ScheduleEntryView[];
  later: ScheduleEntryView[];
  upcoming: ScheduleEntryView[];
}

export interface CountdownLive {
  target: string;
  passed: boolean;
}

export interface ServerCard {
  name: string;
  info: string;
  game_slug: string;
  game_name: string;
  game_short: string;
  color_bg: string;
  color_text: string;
  players_text: string;
}

export interface ServersLive {
  servers?: ServerCard[];
  announcement?: string;
  stale: boolean;
  empty?: boolean;
}

export interface MatchRow {
  id: number | null;
  team1: string;
  team2: string;
  score1: number;
  score2: number;
  start_local: string;
  round: string;
  status: "live" | "scheduled" | "finished" | "waiting";
}

export interface TournamentLive {
  id?: number | null;
  name?: string;
  live?: MatchRow[];
  upcoming?: MatchRow[];
  results?: MatchRow[];
  stale: boolean;
  empty?: boolean;
}

export interface Channel {
  id: string;
  name: string;
  audio_only: boolean;
  thumbnail_url: string;
  watch_url: string;
}

export interface StreamsLive {
  live?: Channel[];
  source_status?: string;
  stale: boolean;
  empty?: boolean;
}

export function asLive<T>(value: unknown): T | null {
  return value && typeof value === "object" ? (value as T) : null;
}
