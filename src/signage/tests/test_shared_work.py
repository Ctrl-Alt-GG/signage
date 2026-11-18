"""Screens poll their bundle all the time. A bundle is built once for all of them, its slides
share what it reads, and its clock is the time it is sent."""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.urls import reverse

from signage.integrations.base import IntegrationClient
from signage.models import Event, Phase, Screen
from signage.rendering import bundle as rendering
from signage.rendering.bundle import build_bundle, shared_bundle

WAIT = 5


@pytest.fixture(autouse=True)
def clear_cache(settings, tmp_path):
    settings.SIGNAGE_LOCK_DIR = str(tmp_path / "locks")
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def slow_build(monkeypatch):
    """A build that takes until the test lets it finish, and counts how often it ran."""
    state = SimpleNamespace(builds=0, started=threading.Event(), finish=threading.Event())

    def build(screen, now, **kwargs):
        state.builds += 1
        state.started.set()
        assert state.finish.wait(WAIT)
        return {"built": state.builds}

    monkeypatch.setattr(rendering, "build_bundle", build)
    return state


def test_requests_for_a_bundle_nobody_has_yet_build_it_once(screen, at, slow_build):
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(shared_bundle, screen, at(1))
        assert slow_build.started.wait(WAIT)
        second = pool.submit(shared_bundle, screen, at(1))
        slow_build.finish.set()
        assert first.result(WAIT) == second.result(WAIT) == {"built": 1}
    assert slow_build.builds == 1


def test_while_a_bundle_is_rebuilt_the_others_get_the_one_before_it(screen, at, slow_build):
    cache.set(f"signage:bundle:{screen.pk}:last", {"built": 0})
    with ThreadPoolExecutor(max_workers=1) as pool:
        rebuilding = pool.submit(shared_bundle, screen, at(1))
        assert slow_build.started.wait(WAIT)
        assert shared_bundle(screen, at(1)) == {"built": 0}
        slow_build.finish.set()
        assert rebuilding.result(WAIT) == {"built": 1}
    assert shared_bundle(screen, at(1)) == {"built": 1}
    assert slow_build.builds == 1


def test_when_the_first_build_fails_the_next_request_builds(screen, at, monkeypatch):
    attempts = []

    def build(screen, now, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("the database went away")
        return {"built": len(attempts)}

    monkeypatch.setattr(rendering, "build_bundle", build)
    with pytest.raises(RuntimeError):
        shared_bundle(screen, at(1))
    assert shared_bundle(screen, at(1)) == {"built": 2}


def test_the_clock_of_an_answer_is_the_time_it_is_sent(client, content, monkeypatch):
    """A cold bundle can wait seconds for the upstream systems. A screen setting its clock
    by when the build began would be that much behind."""
    from signage.api import views

    began = datetime.fromisoformat("2026-10-03T19:00:00+00:00")
    sent = began + timedelta(seconds=5)
    times = iter([began, sent])
    monkeypatch.setattr(views, "timezone", SimpleNamespace(now=lambda: next(times)))
    answer = client.get("/api/v1/screens/main/bundle/").json()
    assert datetime.fromisoformat(answer["clock"]["now"]) == sent
    assert datetime.fromisoformat(answer["generated_at"]) == sent


def test_the_slides_of_a_bundle_share_the_schedule(event, screen, at, monkeypatch):
    event.phase_mode = Event.PhaseMode.MANUAL
    event.current_phase = Phase.objects.get(key="play")
    event.save()
    builds = []
    real = rendering.build_schedule_view
    monkeypatch.setattr(
        rendering, "build_schedule_view", lambda *args: builds.append(1) or real(*args)
    )
    bundle = build_bundle(screen, at(1))
    shown = {p["slide"] for p in bundle["passes"] if p["source"] == "live:schedule"}
    assert shown == {"now_next", "schedule_upcoming"}
    assert len(builds) == 1


def test_the_overview_asks_each_upstream_once_for_all_screens(admin_client, content, monkeypatch):
    from signage.tests.helpers import configure

    configure("projectile", "https://servers.example/api", mirror_announcement=True)
    Screen.objects.create(slug="lobby", name="Lobby")
    Screen.objects.create(slug="stage", name="Stage")
    asked = []
    monkeypatch.setattr(
        IntegrationClient,
        "fetch",
        lambda self, deadline=None: asked.append(self.kind) or rendering.Result(None, True, None),
    )
    assert admin_client.get(reverse("admin:signage_overview")).status_code == 200
    assert asked.count("projectile") == 1
