"""Bracket: the tournament system. Reads one tournament, chosen in the admin, from the
public endpoints. Match status follows Bracket's own pages, so a screen and a phone never
disagree about what is being played."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
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


def _team_name(stage_input: dict[str, Any] | None) -> str:
    """The team in a slot. A slot that waits for the outcome of an earlier stage has none."""
    team = (stage_input or {}).get("team") or {}
    return str(team["name"]) if team.get("name") else ""


def is_played(match: dict[str, Any]) -> bool:
    played = match.get("played")
    if played is None:
        # A Bracket from before it could tell a 0-0 result from a match without one.
        return bool(match.get("stage_item_input1_score") or match.get("stage_item_input2_score"))
    return bool(played)


def match_status(match: dict[str, Any], now: datetime) -> str:
    """`finished` with a result, `waiting` until both teams are known, `scheduled` before
    the planned start. After that the match is `live` during its planned time and
    `awaiting` its result from then on: matches run over, and one that has started is not
    upcoming again."""
    if is_played(match):
        return "finished"
    if not (
        _team_name(match.get("stage_item_input1")) and _team_name(match.get("stage_item_input2"))
    ):
        return "waiting"
    start = _parse(match.get("start_time"))
    if start is None or now < start:
        return "scheduled"
    duration = timedelta(minutes=int(match.get("duration_minutes") or 0))
    return "live" if now < start + duration else "awaiting"


def flatten_matches(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    for stage in stages:
        for item in stage.get("stage_items") or []:
            for round_ in item.get("rounds") or []:
                # Organizers see drafts of a round before they publish it. The public
                # endpoints leave them out, and so does this, whatever the answer holds.
                if round_.get("is_draft"):
                    continue
                for match in round_.get("matches") or []:
                    matches.append({**match, "_round": round_.get("name") or ""})
    return matches


def parse_tournament(
    tournament: dict[str, Any],
    stages: list[dict[str, Any]],
    now: datetime,
    tz: ZoneInfo,
) -> dict[str, Any]:
    far_future = datetime.max.replace(tzinfo=UTC)
    rows = []
    for match in flatten_matches(stages):
        start = _parse(match.get("start_time"))
        rows.append(
            {
                "id": match.get("id"),
                "team1": _team_name(match.get("stage_item_input1")) or "TBD",
                "team2": _team_name(match.get("stage_item_input2")) or "TBD",
                "score1": match.get("stage_item_input1_score") or 0,
                "score2": match.get("stage_item_input2_score") or 0,
                "start_local": start.astimezone(tz).strftime("%H:%M") if start else "",
                "round": match["_round"],
                "status": match_status(match, now),
                "_start": start or far_future,
            }
        )
    rows.sort(key=lambda row: row["_start"])
    # What is being played now comes before what only waits for its result, latest first.
    live = [row for row in rows if row["status"] == "live"]
    awaiting = [row for row in reversed(rows) if row["status"] == "awaiting"]
    parsed = {
        "id": tournament.get("id"),
        "name": tournament.get("name") or "",
        "live": [*live, *awaiting],
        "upcoming": [row for row in rows if row["status"] == "scheduled"][:UPCOMING_LIMIT],
        "results": [row for row in rows if row["status"] == "finished"][-RESULTS_LIMIT:],
    }
    for row in rows:
        row.pop("_start")
    return parsed


class BracketClient(IntegrationClient[dict[str, Any]]):
    kind = Integration.Kind.BRACKET

    def _tournament(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """The tournament and its stages, as anyone may see them."""
        assert self.config is not None
        prefix = f"/tournaments/{self.config.tournament_id}"
        try:
            details = self.get_json(f"{prefix}/details")["data"]
        except httpx.HTTPStatusError as error:
            if error.response.status_code != httpx.codes.NOT_FOUND:
                raise
        else:
            return details["tournament"], details["stages"]
        # A Bracket from before it had the endpoint above. Without `no_draft_rounds` it
        # refuses to answer anyone who is not an organizer.
        tournament = self.get_json(prefix)["data"]
        stages = self.get_json(f"{prefix}/stages", no_draft_rounds="true")["data"]
        return tournament, stages

    def _request(self) -> dict[str, Any]:
        from signage.models import Event

        tournament, stages = self._tournament()
        return parse_tournament(tournament, stages, datetime.now(UTC), Event.get_solo().tz)
