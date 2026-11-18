"""One fetch of an upstream is one operation: its requests, its redirects and the reading of
its answers share the time it has, and no answer may be larger than its format allows."""

import httpx
import pytest
import respx
from django.core.cache import cache

from signage.integrations.base import AnswerTooLargeError, OperationTimeout
from signage.integrations.bracket import BracketClient
from signage.integrations.projectile import ProjectileClient
from signage.integrations.streams import StreamsClient
from signage.tests.helpers import BRACKET, FakeClock, configure


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def taking(clock: FakeClock, seconds: float, response: httpx.Response):
    """An upstream that answers with `response` after `seconds` of the clock."""

    def answer(request):
        clock.advance(seconds)
        return response

    return answer


def trickle(clock: FakeClock, chunk: bytes, seconds_per_chunk: float = 0.0, count=None):
    """A body that keeps coming, a chunk at a time, and counts how much of it was read."""
    read = {"chunks": 0}

    def chunks():
        while count is None or read["chunks"] < count:
            clock.advance(seconds_per_chunk)
            read["chunks"] += 1
            yield chunk

    return chunks(), read


@respx.mock
def test_all_requests_of_a_fetch_share_its_time(content):
    """A Bracket without the details endpoint takes three requests. Six seconds each would
    take eighteen; the operation has ten, and its last request is never made."""
    clock = FakeClock()
    client = BracketClient(configure("bracket", BRACKET, tournament_id=7))
    client.clock = clock
    details = respx.get(f"{BRACKET}/tournaments/7/details").mock(
        side_effect=taking(clock, 6, httpx.Response(404))
    )
    tournament = respx.get(f"{BRACKET}/tournaments/7").mock(
        side_effect=taking(clock, 6, httpx.Response(200, json={"data": {"id": 7}}))
    )
    stages = respx.get(f"{BRACKET}/tournaments/7/stages").mock(
        side_effect=taking(clock, 6, httpx.Response(200, json={"data": []}))
    )

    result = client.fetch(deadline=clock() + 15)

    assert result.data is None and "OperationTimeout" in result.error
    assert (details.call_count, tournament.call_count, stages.call_count) == (1, 1, 0)
    # The second request had what was left of the ten seconds, not a timeout of its own.
    timeout = tournament.calls.last.request.extensions["timeout"]
    assert timeout["read"] == pytest.approx(4)


@respx.mock
def test_a_fetch_has_no_more_time_than_the_bundle_has_left(content, fixture_json):
    clock = FakeClock()
    client = ProjectileClient(configure("projectile", "https://servers.example/api"))
    client.clock = clock
    route = respx.get("https://servers.example/api/bundle").mock(
        return_value=httpx.Response(200, json=fixture_json("projectile_bundle.json"))
    )
    assert client.fetch(deadline=clock() + 1.5).ok
    assert route.calls.last.request.extensions["timeout"]["read"] == pytest.approx(1.5)


@respx.mock
def test_an_answer_that_trickles_in_ends_with_the_operations_time(content):
    clock = FakeClock()
    client = StreamsClient(configure("streams", "https://streams.example/api/v1"))
    client.clock = clock
    body, read = trickle(clock, b" ", seconds_per_chunk=2)
    respx.get("https://streams.example/api/v1/streams/").mock(
        return_value=httpx.Response(200, content=body)
    )
    result = client.fetch()
    assert result.data is None and "OperationTimeout" in result.error
    assert read["chunks"] == 5


@respx.mock
def test_a_redirect_chain_of_a_thumbnail_shares_one_operations_time(content):
    clock = FakeClock()
    client = StreamsClient(configure("streams", "https://streams.example/api/v1"))
    client.clock = clock
    first = respx.get("https://streams.example/t/1").mock(
        side_effect=taking(clock, 4, httpx.Response(302, headers={"Location": "/t/2"}))
    )
    second = respx.get("https://streams.example/t/2").mock(
        side_effect=taking(clock, 4, httpx.Response(302, headers={"Location": "/t/3"}))
    )
    third = respx.get("https://streams.example/t/3").mock(
        side_effect=taking(clock, 4, httpx.Response(302, headers={"Location": "/t/4"}))
    )
    fourth = respx.get("https://streams.example/t/4").respond(
        200, content=b"img", headers={"content-type": "image/webp"}
    )
    with pytest.raises(OperationTimeout):
        client.fetch_bytes("/t/1")
    assert (first.call_count, second.call_count, third.call_count, fourth.call_count) == (
        1,
        1,
        1,
        0,
    )


@respx.mock
def test_an_answer_larger_than_its_format_allows_is_refused_unread(content, settings):
    settings.SIGNAGE_UPSTREAM_MAX_BYTES = 1_000
    client = StreamsClient(configure("streams", "https://streams.example/api/v1"))
    body, read = trickle(FakeClock(), b"x" * 400)
    respx.get("https://streams.example/api/v1/streams/").mock(
        return_value=httpx.Response(200, headers={"content-length": "5000000"}, content=body)
    )
    result = client.fetch()
    assert result.data is None and "AnswerTooLargeError" in result.error
    assert read["chunks"] == 0


@respx.mock
def test_an_answer_without_a_length_is_read_only_up_to_its_limit(content, settings):
    settings.SIGNAGE_UPSTREAM_MAX_BYTES = 1_000
    client = StreamsClient(configure("streams", "https://streams.example/api/v1"))
    body, read = trickle(FakeClock(), b"x" * 400)
    respx.get("https://streams.example/api/v1/streams/").mock(
        return_value=httpx.Response(200, content=body)
    )
    result = client.fetch()
    assert result.data is None and "AnswerTooLargeError" in result.error
    assert read["chunks"] == 3


@respx.mock
def test_a_thumbnail_is_checked_for_its_type_and_size_before_it_is_read(content, settings):
    settings.SIGNAGE_THUMBNAIL_MAX_BYTES = 1_000
    client = StreamsClient(configure("streams", "https://streams.example/api/v1"))
    page, page_read = trickle(FakeClock(), b"<p>" * 100)
    respx.get("https://streams.example/page").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"}, content=page)
    )
    with pytest.raises(ValueError, match="not a picture"):
        client.fetch_bytes("/page")
    assert page_read["chunks"] == 0

    picture, picture_read = trickle(FakeClock(), b"\x00" * 400)
    respx.get("https://streams.example/big.webp").mock(
        return_value=httpx.Response(200, headers={"content-type": "image/webp"}, content=picture)
    )
    with pytest.raises(AnswerTooLargeError):
        client.fetch_bytes("/big.webp")
    assert picture_read["chunks"] == 3
