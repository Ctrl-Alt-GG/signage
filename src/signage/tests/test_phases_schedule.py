from datetime import timedelta

from signage.models import Event, Phase
from signage.rendering.phases import resolve_phase
from signage.rendering.schedule import build_schedule_view


def test_manual_phase_wins(event, at):
    event.phase_mode = Event.PhaseMode.MANUAL
    event.current_phase = Phase.objects.get(key="late")
    event.save()
    assert resolve_phase(event, at(0)).key == "late"


def test_auto_phase_follows_the_clock(event, at):
    event.phase_mode = Event.PhaseMode.AUTO
    event.save()
    assert resolve_phase(event, at(-10)).key == "setup"
    assert resolve_phase(event, at(-0.5)).key == "arrival"
    assert resolve_phase(event, at(0)).key == "play"
    assert resolve_phase(event, at(4.5)).key == "tournament"
    assert resolve_phase(event, at(8)).key == "late"
    assert resolve_phase(event, at(14.5)).key == "morning"
    assert resolve_phase(event, at(16)).key == "teardown"
    assert resolve_phase(event, event.ends_at + timedelta(days=1)).key == "teardown"


def test_schedule_before_the_first_entry(event, at):
    view = build_schedule_view(event, at(-1))
    assert view.now == []
    assert [e.time for e in view.next] == ["15:30"]


def test_schedule_groups_entries_sharing_a_time(event, at):
    view = build_schedule_view(event, at(4.6))
    assert [e.title["en"] for e in view.now] == [
        "The CS2 tournament begins",
        "Build railways while the tournament runs",
    ]
    assert [e.time for e in view.next] == ["22:00"]
    assert [e.time for e in view.later] == ["22:15"]


def test_schedule_crosses_midnight(event, at):
    view = build_schedule_view(event, at(8 + 20 / 60))
    assert [e.time for e in view.now] == ["23:40"]
    assert [e.time for e in view.next] == ["00:00"]
    assert view.next[0].starts_at.startswith(event.starts_at.date().isoformat()) is False


def test_last_entry_stays_current_until_the_end(event, at):
    view = build_schedule_view(event, at(15))
    assert [e.time for e in view.now] == ["06:00"]
    assert view.next == []
    assert build_schedule_view(event, event.ends_at).now == []
