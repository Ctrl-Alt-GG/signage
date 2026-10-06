from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from django.core.cache import cache

from signage.integrations.bracket import BracketClient, match_status, parse_tournament
from signage.integrations.projectile import ProjectileClient, parse_bundle, players_text
from signage.integrations.streams import StreamsClient, parse_streams
from signage.models import Game, Integration


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_parse_projectile_bundle(content, fixture_json):
    parsed = parse_bundle(fixture_json("projectile_bundle.json"), list(Game.objects.all()))
    names = [s["name"] for s in parsed["servers"]]
    assert names == ["Voice", "Blocks", "Office 24/7", "Mystery"]  # by the last octet, unknown last
    office = parsed["servers"][2]
    assert office["game_short"] == "CS2" and office["color_bg"] == "#c9a227"
    assert office["players_text"] == "7 / 12"
    assert parsed["servers"][0]["players_text"] == "max: 64"
    assert parsed["servers"][3]["game_name"] == "unknowngame"
    assert parsed["announcement"].startswith("Pizza")


def test_players_text_without_count():
    assert players_text({"max_players": 10, "capabilities": {}}) == "max: 10"
    assert players_text({"capabilities": {}}) == ""


def test_parse_streams(fixture_json):
    parsed = parse_streams(fixture_json("streams_list.json"))
    assert [c["name"] for c in parsed["live"]] == ["Main stage", "radio"]
    assert parsed["live"][1]["audio_only"] is True
    assert parsed["source_status"] == "fresh"


def test_match_status_rules():
    now = datetime(2026, 10, 3, 18, 50, tzinfo=UTC)
    base = {"stage_item_input1": {}, "stage_item_input2": {}, "duration_minutes": 30}
    assert match_status({**base, "stage_item_input1_score": 16}, now) == "finished"
    assert match_status({**base, "stage_item_input2": None}, now) == "waiting"
    assert match_status({**base, "start_time": "2026-10-03T18:40:00Z"}, now) == "live"
    assert match_status({**base, "start_time": "2026-10-03T20:00:00Z"}, now) == "scheduled"
    assert match_status({**base, "start_time": None}, now) == "scheduled"


def test_parse_tournament(fixture_json):
    now = datetime(2026, 10, 3, 18, 50, tzinfo=UTC)
    parsed = parse_tournament(
        fixture_json("bracket_tournaments.json")["data"][0],
        fixture_json("bracket_stages.json")["data"],
        fixture_json("bracket_teams.json")["data"],
        now,
        ZoneInfo("Europe/Budapest"),
    )
    assert parsed["name"] == "CS2 Autumn 2026"
    assert [(m["team1"], m["team2"], m["start_local"]) for m in parsed["live"]] == [
        ("Eco Round", "Clutch Kings", "20:40")
    ]
    assert [m["start_local"] for m in parsed["upcoming"]] == ["22:30"]
    assert parsed["results"][0]["score1"] == 16


def _configure(kind: str, url: str) -> Integration:
    row = Integration.objects.get(kind=kind)
    row.enabled = True
    row.base_url = url
    row.auth_type = Integration.Auth.BASIC
    row.username = "u"
    row.password = "p"
    row.save()
    return row


@respx.mock
def test_fetch_caches_and_falls_back_to_last_good(content, fixture_json):
    row = _configure("projectile", "https://servers.example/api")
    route = respx.get("https://servers.example/api/bundle").mock(
        return_value=httpx.Response(200, json=fixture_json("projectile_bundle.json"))
    )
    client = ProjectileClient(row)
    first = client.fetch()
    assert first.ok and not first.stale and len(first.data["servers"]) == 4
    assert route.calls.last.request.headers["Authorization"].startswith("Basic ")
    client.fetch()
    assert route.call_count == 1  # served from the cache
    cache.delete(client.cache_key)
    route.mock(return_value=httpx.Response(500))
    stale = client.fetch()
    assert stale.ok and stale.stale and stale.error == "HTTPStatusError"


@respx.mock
def test_fetch_without_any_cache_returns_empty(content):
    row = _configure("streams", "https://streams.example/api/v1")
    respx.get("https://streams.example/api/v1/streams/").mock(side_effect=httpx.ConnectError("x"))
    result = StreamsClient(row).fetch()
    assert result.data is None and result.stale and result.error == "ConnectError"


def test_disabled_integration_is_skipped(content):
    result = BracketClient(Integration.objects.get(kind="bracket")).fetch()
    assert result.data is None and result.error == "disabled"


@respx.mock
def test_bracket_client_picks_the_first_open_tournament(content, fixture_json):
    row = _configure("bracket", "https://bracket.example/api")
    row.auth_type = Integration.Auth.NONE
    row.save()
    respx.get("https://bracket.example/api/tournaments").mock(
        return_value=httpx.Response(200, json=fixture_json("bracket_tournaments.json"))
    )
    respx.get("https://bracket.example/api/tournaments/3/stages").mock(
        return_value=httpx.Response(200, json=fixture_json("bracket_stages.json"))
    )
    respx.get("https://bracket.example/api/tournaments/3/teams").mock(
        return_value=httpx.Response(200, json=fixture_json("bracket_teams.json"))
    )
    result = BracketClient(row).fetch()
    assert result.ok and result.data["id"] == 3
