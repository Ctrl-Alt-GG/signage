"""What Signage makes of Streams' answers. Streams says whether it could check its media
server (`source.status`) and how long ago (`source.age_seconds`); an answer it can't vouch
for must not replace the channels it last confirmed, and those may only stand in while they
are recent."""

from datetime import timedelta

import httpx
import pytest
import respx
from django.core.cache import cache

from signage.integrations.streams import StreamsClient
from signage.models import Slide
from signage.rendering.bundle import RenderContext, live_data
from signage.tests.helpers import configure

LIST = "https://streams.example/api/v1/streams/"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def channel(number: int, status: str = "live") -> dict:
    return {
        "id": f"id-{number}",
        "effective_name": f"Stage {number}",
        "status": status,
        "audio_only": False,
        "thumbnail_url": f"https://streams.example/streams/{number}/thumbnail/",
        "watch_url": f"https://streams.example/streams/{number}/",
    }


def answer(status: str, *channels: dict, age: float | None = 2.0) -> httpx.Response:
    source = {"status": status, "observed_at": "2026-10-03T19:02:10+00:00", "failure_count": 0}
    if age is not None:
        source["age_seconds"] = age
    return httpx.Response(200, json={"source": source, "results": list(channels)})


@pytest.fixture
def streams(content):
    client = StreamsClient(configure("streams", "https://streams.example/api/v1"))
    route = respx.get(LIST)

    def ask(response: httpx.Response):
        """The next answer of Streams, as the next fetch after the cache period gets it."""
        cache.delete(client.cache_key)
        route.mock(return_value=response)
        return client.fetch()

    return client, ask


def names(result) -> list[str]:
    return [item["name"] for item in result.data["live"]]


@respx.mock
def test_a_fresh_answer_is_shown_as_it_is(streams):
    _, ask = streams
    result = ask(answer("fresh", channel(1), channel(2, "offline")))
    assert names(result) == ["Stage 1"] and not result.stale
    assert result.data["observed_at"] == "2026-10-03T19:02:10+00:00"


@respx.mock
def test_a_fresh_answer_without_live_channels_replaces_the_previous_ones(streams):
    _, ask = streams
    ask(answer("fresh", channel(1)))
    result = ask(answer("fresh", channel(1, "offline")))
    assert names(result) == [] and not result.stale


@respx.mock
def test_a_stale_observation_is_shown_as_not_current(streams):
    _, ask = streams
    result = ask(answer("stale", channel(1), age=40))
    assert names(result) == ["Stage 1"] and result.stale


@respx.mock
def test_an_unavailable_source_keeps_the_last_confirmed_channels(streams):
    client, ask = streams
    ask(answer("fresh", channel(1)))
    confirmed = cache.get(f"{client.cache_key}:last")
    result = ask(answer("unavailable", channel(1, "unknown"), age=None))
    assert names(result) == ["Stage 1"] and result.stale
    assert cache.get(f"{client.cache_key}:last") == confirmed
    # A thumbnail is looked up among the same channels as the screen shows.
    assert client.thumbnail_source("id-1") == "https://streams.example/streams/1/thumbnail/"


@respx.mock
def test_an_unavailable_source_without_earlier_channels_says_so(streams):
    _, ask = streams
    result = ask(answer("unavailable", channel(1, "unknown"), age=None))
    assert result.stale
    assert result.data["live"] == [] and result.data["source_status"] == "unavailable"


@respx.mock
def test_an_answer_streams_does_not_describe_counts_as_unavailable(streams):
    _, ask = streams
    result = ask(answer("rebooting", channel(1)))
    assert result.data["live"] == [] and result.data["source_status"] == "unavailable"


@respx.mock
def test_confirmed_channels_stand_in_only_while_they_are_recent(streams, settings):
    client, ask = streams
    settings.SIGNAGE_STREAMS_RETAIN_SECONDS = 300
    ask(answer("fresh", channel(1), age=100))
    # Fetched three minutes ago: the observation is 280 seconds old now.
    last = cache.get(f"{client.cache_key}:last")
    last["fetched_at"] -= timedelta(minutes=3)
    cache.set(f"{client.cache_key}:last", last)
    assert names(ask(answer("unavailable", age=None))) == ["Stage 1"]
    # A minute later it is 340 seconds old, and the screen says that it can't tell.
    last["fetched_at"] -= timedelta(minutes=1)
    cache.set(f"{client.cache_key}:last", last)
    result = ask(answer("unavailable", age=None))
    assert result.data["live"] == [] and result.data["source_status"] == "unavailable"


@respx.mock
def test_repeated_answers_of_one_stale_observation_do_not_make_it_recent(streams, settings):
    _, ask = streams
    settings.SIGNAGE_STREAMS_RETAIN_SECONDS = 300
    assert names(ask(answer("stale", channel(1), age=200))) == ["Stage 1"]
    # Streams counts the age of its last check, however often it is asked.
    result = ask(answer("stale", channel(1), age=320))
    assert result.data["live"] == [] and result.data["source_status"] == "unavailable"


@respx.mock
def test_the_channels_come_back_when_streams_can_check_again(streams):
    _, ask = streams
    ask(answer("unavailable", age=None))
    result = ask(answer("fresh", channel(2)))
    assert names(result) == ["Stage 2"] and not result.stale


@respx.mock
def test_the_screen_marks_retained_channels_and_an_unavailable_source(streams, event):
    _, ask = streams
    slide = Slide.objects.get(pk="streams_live")
    ask(answer("fresh", channel(1)))
    cache.delete(StreamsClient().cache_key)
    respx.get(LIST).mock(return_value=answer("unavailable", age=None))
    retained = live_data(slide, RenderContext.load(event.starts_at), [])
    assert [item["name"] for item in retained["live"]] == ["Stage 1"] and retained["stale"]

    cache.clear()
    gone = live_data(slide, RenderContext.load(event.starts_at), [])
    assert gone["live"] == [] and gone["stale"] and gone["source_status"] == "unavailable"
