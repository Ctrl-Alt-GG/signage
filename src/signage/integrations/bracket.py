"""Bracket: the tournament system. Public endpoints for open tournaments; match status
is derived the way Bracket's own frontend does it."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.utils.dateparse import parse_datetime

from signage.integrations.base import IntegrationClient
from signage.models import Integration

UPCOMING_LIMIT = 4
RESULTS_LIMIT = 3


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _team_name(stage_input: dict[str, Any] | None, teams: dict[int, str]) -> str:
    if not stage_input:
        return "TBD"
    team = stage_input.get("team") or {}
    if team.get("name"):
        return str(team["name"])
    team_id = stage_input.get("team_id")
    return teams.get(team_id, "TBD") if team_id is not None else "TBD"


def match_status(match: dict[str, Any], now: datetime) -> str:
    if match.get("stage_item_input1_score") or match.get("stage_item_input2_score"):
        return "finished"
    if match.get("stage_item_input1") is None or match.get("stage_item_input2") is None:
        return "waiting"
    start = _parse(match.get("start_time"))
    if start is not None:
        duration = timedelta(minutes=int(match.get("duration_minutes") or 0))
        if start <= now < start + duration:
            return "live"
    return "scheduled"


def flatten_matches(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    for stage in stages:
        for item in stage.get("stage_items") or []:
            for round_ in item.get("rounds") or []:
                for match in round_.get("matches") or []:
                    matches.append({**match, "_round": round_.get("name") or ""})
    return matches


def parse_tournament(
    tournament: dict[str, Any],
    stages: list[dict[str, Any]],
    teams_payload: list[dict[str, Any]],
    now: datetime,
    tz: ZoneInfo,
) -> dict[str, Any]:
    teams = {int(t["id"]): str(t.get("name") or "?") for t in teams_payload if "id" in t}
    rows = []
    for match in flatten_matches(stages):
        start = _parse(match.get("start_time"))
        rows.append(
            {
                "id": match.get("id"),
                "team1": _team_name(match.get("stage_item_input1"), teams),
                "team2": _team_name(match.get("stage_item_input2"), teams),
                "score1": match.get("stage_item_input1_score") or 0,
                "score2": match.get("stage_item_input2_score") or 0,
                "start_local": start.astimezone(tz).strftime("%H:%M") if start else "",
                "round": match["_round"],
                "status": match_status(match, now),
                "_start": start,
            }
        )
    far_future = datetime.max.replace(tzinfo=UTC)
    rows.sort(key=lambda row: row["_start"] or far_future)
    for row in rows:
        row.pop("_start")
    return {
        "id": tournament.get("id"),
        "name": tournament.get("name") or "",
        "live": [r for r in rows if r["status"] == "live"],
        "upcoming": [r for r in rows if r["status"] == "scheduled"][:UPCOMING_LIMIT],
        "results": [r for r in rows if r["status"] == "finished"][-RESULTS_LIMIT:],
    }


class BracketClient(IntegrationClient[dict[str, Any]]):
    kind = Integration.Kind.BRACKET

    def _pick_tournament(self) -> dict[str, Any] | None:
        assert self.config is not None
        if self.config.tournament_id:
            payload = self.get_json(f"/tournaments/{self.config.tournament_id}")
            return payload.get("data")
        payload = self.get_json("/tournaments", filter_="OPEN")
        tournaments = payload.get("data") or []
        return tournaments[0] if tournaments else None

    def _request(self) -> dict[str, Any]:
        from signage.models import Event

        tournament = self._pick_tournament()
        if tournament is None:
            return {"id": None, "name": "", "live": [], "upcoming": [], "results": []}
        tournament_id = tournament["id"]
        stages = self.get_json(f"/tournaments/{tournament_id}/stages").get("data") or []
        teams = self.get_json(f"/tournaments/{tournament_id}/teams").get("data") or []
        return parse_tournament(tournament, stages, teams, datetime.now(UTC), Event.get_solo().tz)
