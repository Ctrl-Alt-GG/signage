from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from django.core.cache import cache

from signage.integrations.base import refresh_lock
from signage.integrations.bracket import BracketClient, match_status, parse_tournament
from signage.integrations.projectile import ProjectileClient, parse_bundle, players_text
from signage.integrations.streams import StreamsClient, parse_streams
from signage.models import Game, Integration

BUDAPEST = ZoneInfo("Europe/Budapest")


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


# ---------------------------------------------------------------- Bracket


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 10, 3, hour, minute, tzinfo=UTC)


def test_match_status_rules():
    team = {"team": {"name": "Eco Round"}}
    base = {
        "stage_item_input1": team,
        "stage_item_input2": team,
        "duration_minutes": 30,
        "start_time": "2026-10-03T18:35:00Z",
        "played": False,
    }
    assert match_status(base, _at(18, 0)) == "scheduled"
    assert match_status(base, _at(18, 50)) == "live"
    # It ran over, or its result was not entered yet: it has started, so it is not
    # upcoming again.
    assert match_status(base, _at(20, 0)) == "awaiting"
    assert match_status({**base, "played": True}, _at(18, 0)) == "finished"
    assert match_status({**base, "start_time": None}, _at(18, 50)) == "scheduled"
    # A slot that takes the winner of a group has no team until the group is decided.
    undecided = {"winner_from_stage_item_id": 1, "winner_position": 1, "team": None}
    assert match_status({**base, "stage_item_input2": undecided}, _at(20, 0)) == "waiting"
    assert match_status({**base, "stage_item_input2": None}, _at(20, 0)) == "waiting"


def test_match_status_reads_a_bracket_without_the_played_marker():
    team = {"team": {"name": "Eco Round"}}
    old = {"stage_item_input1": team, "stage_item_input2": team, "start_time": None}
    assert match_status({**old, "stage_item_input1_score": 16}, _at(18, 0)) == "finished"
    assert match_status({**old, "stage_item_input1_score": 0}, _at(18, 0)) == "scheduled"


def test_parse_tournament_from_a_recorded_answer(fixture_json):
    details = fixture_json("bracket_details.json")["data"]
    parsed = parse_tournament(details["tournament"], details["stages"], _at(18, 50), BUDAPEST)

    assert parsed["name"] == "CS2 Autumn 2026"
    # The second round is being played. Its matches have no result yet.
    assert [(m["team1"], m["team2"], m["start_local"], m["status"]) for m in parsed["live"]] == [
        ("Eco Round", "Rush B", "20:35", "live"),
        ("Smoke Mid", "Clutch Kings", "20:35", "live"),
    ]
    assert [m["start_local"] for m in parsed["upcoming"]] == ["21:10", "21:10"]
    # The final waits for the group to finish, so nobody is announced for it.
    assert all("TBD" not in (m["team1"], m["team2"]) for m in parsed["upcoming"])
    # A goalless draw is a result: Bracket says so, the scores alone do not.
    assert [(m["team1"], m["score1"], m["score2"], m["team2"]) for m in parsed["results"]] == [
        ("Eco Round", 16, 9, "Smoke Mid"),
        ("Clutch Kings", 0, 0, "Rush B"),
    ]


def test_parse_tournament_keeps_started_matches_out_of_the_upcoming_list(fixture_json):
    details = fixture_json("bracket_details.json")["data"]
    parsed = parse_tournament(details["tournament"], details["stages"], _at(19, 20), BUDAPEST)

    # The third round is on. The second is over by the plan and still without results.
    assert [(m["start_local"], m["status"]) for m in parsed["live"]] == [
        ("21:10", "live"),
        ("21:10", "live"),
        ("20:35", "awaiting"),
        ("20:35", "awaiting"),
    ]
    assert parsed["upcoming"] == []


def test_draft_rounds_are_never_shown(fixture_json):
    details = fixture_json("bracket_details.json")["data"]
    for stage in details["stages"]:
        for item in stage["stage_items"]:
            for round_ in item["rounds"]:
                round_["is_draft"] = True
    parsed = parse_tournament(details["tournament"], details["stages"], _at(18, 50), BUDAPEST)
    assert parsed["live"] == parsed["upcoming"] == parsed["results"] == []


def test_all_live_matches_reach_the_display_paginator():
    matches = [
        {
            "id": i,
            "played": False,
            "start_time": "2026-10-03T18:35:00Z",
            "duration_minutes": 30,
            "stage_item_input1": {"team": {"name": f"ALPHA-{i}"}},
            "stage_item_input2": {"team": {"name": f"BETA-{i}"}},
        }
        for i in range(1, 7)
    ]
    stages = [{"stage_items": [{"rounds": [{"name": "Group", "matches": matches}]}]}]
    parsed = parse_tournament({"id": 1, "name": "Event"}, stages, _at(18, 50), BUDAPEST)
    assert [match["id"] for match in parsed["live"]] == list(range(1, 7))


def _configure(kind: str, url: str, **values) -> Integration:
    row = Integration.objects.get(kind=kind)
    row.enabled = True
    row.base_url = url
    for name, value in values.items():
        setattr(row, name, value)
    row.full_clean()
    row.save()
    return row


BASIC = {"auth_type": Integration.Auth.BASIC, "username": "u", "password": "p"}
BRACKET = "https://bracket.example/api"


@respx.mock
def test_bracket_client_reads_the_chosen_tournament(content, fixture_json):
    row = _configure("bracket", BRACKET, tournament_id=1)
    details = respx.get(f"{BRACKET}/tournaments/1/details").mock(
        return_value=httpx.Response(200, json=fixture_json("bracket_details.json"))
    )
    result = BracketClient(row).fetch()
    assert result.ok and result.data["id"] == 1 and result.data["name"] == "CS2 Autumn 2026"
    assert details.call_count == 1


@respx.mock
def test_bracket_client_reads_a_bracket_from_before_the_details_endpoint(content, fixture_json):
    row = _configure("bracket", BRACKET, tournament_id=1)
    respx.get(f"{BRACKET}/tournaments/1/details").mock(
        return_value=httpx.Response(404, json={"detail": "Not Found"})
    )
    respx.get(f"{BRACKET}/tournaments/1").mock(
        return_value=httpx.Response(200, json=fixture_json("bracket_tournament.json"))
    )
    # Without the parameter Bracket answers 403 to anyone who is not an organizer.
    stages = respx.get(f"{BRACKET}/tournaments/1/stages", params={"no_draft_rounds": "true"}).mock(
        return_value=httpx.Response(200, json=fixture_json("bracket_stages.json"))
    )
    result = BracketClient(row).fetch()
    assert result.ok and result.data["name"] == "CS2 Autumn 2026"
    assert stages.call_count == 1
    assert len(result.data["results"]) == 2


def test_bracket_never_guesses_a_tournament(content):
    row = Integration.objects.get(kind="bracket")
    row.enabled = True
    row.base_url = BRACKET
    with pytest.raises(Exception, match="Choose the tournament"):
        row.full_clean()
    row.save()
    client = BracketClient(row)
    assert not client.enabled and client.fetch().error == "disabled"


def test_recorded_answers_match_brackets_own_schema(fixture_json):
    """The fixtures are answers recorded from Bracket. This keeps them, and with them the
    parser, in step with the API as Bracket documents it."""
    from jsonschema import Draft202012Validator

    document = fixture_json("bracket_openapi.json")
    for name, fixture in (
        ("details", "bracket_details.json"),
        ("tournament", "bracket_tournament.json"),
        ("stages", "bracket_stages.json"),
    ):
        # The answer's schema points into `#/components`, so it is checked from inside
        # the document those pointers refer to.
        validator = Draft202012Validator({**document, **document["responses"][name]})
        errors = [error.message for error in validator.iter_errors(fixture_json(fixture))]
        assert errors == [], f"{fixture}: {errors[:3]}"


def test_the_fields_the_parser_reads_are_in_brackets_schema(fixture_json):
    schemas = fixture_json("bracket_openapi.json")["components"]["schemas"]

    def has(schema: str, *fields: str) -> bool:
        return set(fields) <= set(schemas[schema]["properties"])

    assert has("TournamentDetails", "tournament", "stages")
    assert has("Tournament", "id", "name")
    assert has("StageWithStageItems", "stage_items")
    assert has("StageItemWithRounds", "rounds")
    assert has("RoundWithMatches", "name", "is_draft", "matches")
    for match in ("MatchWithDetails", "MatchWithDetailsDefinitive"):
        assert has(
            match,
            "id",
            "start_time",
            "duration_minutes",
            "played",
            "stage_item_input1",
            "stage_item_input2",
            "stage_item_input1_score",
            "stage_item_input2_score",
        )
    assert has("StageItemInputFinal", "team") and has("Team", "name")


# ---------------------------------------------------------------- caching


@respx.mock
def test_fetch_caches_and_falls_back_to_last_good(content, fixture_json):
    row = _configure("projectile", "https://servers.example/api", **BASIC)
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
    assert stale.ok and stale.stale
    # The log and the admin say what went wrong, not only that something did.
    assert "HTTPStatusError" in stale.error and "500" in stale.error


@respx.mock
def test_an_upstream_that_is_down_is_asked_once_per_cache_period(content):
    row = _configure("streams", "https://streams.example/api/v1")
    route = respx.get("https://streams.example/api/v1/streams/").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    client = StreamsClient(row)
    first = client.fetch()
    assert first.data is None and first.stale and "ConnectError" in first.error
    # Every screen polls. The next ones get the same answer without waiting for a timeout.
    again = StreamsClient(row).fetch()
    assert again.data is None and "ConnectError" in again.error
    assert route.call_count == 1
    assert client.status()["error"] == first.error


@respx.mock
def test_one_request_refreshes_while_the_others_get_the_last_good_answer(content, fixture_json):
    row = _configure("projectile", "https://servers.example/api")
    route = respx.get("https://servers.example/api/bundle").mock(
        return_value=httpx.Response(200, json=fixture_json("projectile_bundle.json"))
    )
    client = ProjectileClient(row)
    client.fetch()
    cache.delete(client.cache_key)
    # Another request is asking the upstream right now.
    cache.set(f"{client.cache_key}:fetching", True, 30)
    waiting = client.fetch()
    assert waiting.ok and waiting.stale and waiting.error == "refreshing"
    assert route.call_count == 1


def test_refresh_lock_is_shared_between_threads_and_released(settings, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    settings.SIGNAGE_LOCK_DIR = str(tmp_path / "locks")

    def competing() -> bool:
        with refresh_lock("streams-test") as acquired:
            return acquired

    with ThreadPoolExecutor(max_workers=1) as pool:
        with refresh_lock("streams-test") as acquired:
            assert acquired
            assert pool.submit(competing).result(timeout=1) is False
        assert pool.submit(competing).result(timeout=1) is True


@respx.mock
def test_new_settings_never_get_an_answer_from_the_old_ones(content, fixture_json):
    old = _configure("bracket", BRACKET, tournament_id=1)
    respx.get(f"{BRACKET}/tournaments/1/details").mock(
        return_value=httpx.Response(200, json=fixture_json("bracket_details.json"))
    )
    assert BracketClient(old).fetch().ok

    other = fixture_json("bracket_details.json")
    other["data"]["tournament"]["name"] = "Another tournament"
    respx.get(f"{BRACKET}/tournaments/2/details").mock(return_value=httpx.Response(200, json=other))
    new = _configure("bracket", BRACKET, tournament_id=2)
    assert BracketClient(new).fetch().data["name"] == "Another tournament"

    # Nor is the old tournament shown as "last good" when the new one cannot be read.
    respx.get(f"{BRACKET}/tournaments/3/details").mock(return_value=httpx.Response(500))
    third = BracketClient(_configure("bracket", BRACKET, tournament_id=3)).fetch()
    assert third.data is None and third.stale


@respx.mock
def test_credentials_do_not_follow_a_redirect(content):
    row = _configure("projectile", "https://servers.example/api", **BASIC)
    respx.get("https://servers.example/api/bundle").mock(
        return_value=httpx.Response(302, headers={"Location": "https://evil.example/bundle"})
    )
    elsewhere = respx.get("https://evil.example/bundle").mock(return_value=httpx.Response(200))
    result = ProjectileClient(row).fetch()
    assert result.data is None and elsewhere.call_count == 0


def test_disabled_integration_is_skipped(content):
    result = BracketClient(Integration.objects.get(kind="bracket")).fetch()
    assert result.data is None and result.error == "disabled"


# ---------------------------------------------------------------- thumbnails


@respx.mock
def test_thumbnails_come_from_the_address_streams_was_configured_with(content):
    """Streams names its public address in the URLs it hands out. Signage may reach it by
    another one, and that is where the credentials belong."""
    client = StreamsClient(_configure("streams", "http://streams-web:8000/api/v1", **BASIC))
    internal = respx.get("http://streams-web:8000/streams/1/thumbnail/").respond(
        200, content=b"img", headers={"content-type": "image/jpeg"}
    )
    public = respx.get("https://streams.example/streams/1/thumbnail/").respond(200)

    assert client.fetch_bytes("https://streams.example/streams/1/thumbnail/") == (
        b"img",
        "image/jpeg",
    )
    assert client.fetch_bytes("/streams/1/thumbnail/") == (b"img", "image/jpeg")
    assert internal.call_count == 2 and public.call_count == 0
    assert internal.calls.last.request.headers["Authorization"].startswith("Basic ")


@respx.mock
def test_thumbnail_redirects_stay_with_streams(content):
    client = StreamsClient(_configure("streams", "https://streams.example/api", **BASIC))
    respx.get("https://streams.example/streams/1/thumbnail/").mock(
        return_value=httpx.Response(302, headers={"Location": "https://cdn.example/t/1.jpg?x=1"})
    )
    on_streams = respx.get("https://streams.example/t/1.jpg", params={"x": "1"}).respond(
        200, content=b"img", headers={"content-type": "image/jpeg; charset=binary"}
    )
    elsewhere = respx.get("https://cdn.example/t/1.jpg").respond(200)

    assert client.fetch_bytes("/streams/1/thumbnail/") == (b"img", "image/jpeg")
    assert on_streams.call_count == 1 and elsewhere.call_count == 0


@respx.mock
def test_only_pictures_are_passed_on_as_thumbnails(content):
    client = StreamsClient(_configure("streams", "https://streams.example/api"))
    respx.get("https://streams.example/page").respond(
        200, content=b"<script>alert(1)</script>", headers={"content-type": "text/html"}
    )
    with pytest.raises(ValueError, match="not a picture"):
        client.fetch_bytes("/page")
    for url in ("ftp://streams.example/x.jpg", "javascript:alert(1)", "x.jpg"):
        with pytest.raises(ValueError, match="not a thumbnail address"):
            client.fetch_bytes(url)
