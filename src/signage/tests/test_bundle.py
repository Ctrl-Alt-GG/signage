from datetime import timedelta

import pytest
from django.utils import timezone

from signage.models import Announcement, Event, Integration, Phase, Screen, ScreenSlide, Slide
from signage.rendering.bundle import build_bundle


def _slides(bundle):
    return sorted({p["slide"] for p in bundle["passes"]})


def _set_phase(event, key):
    event.phase_mode = Event.PhaseMode.MANUAL
    event.current_phase = Phase.objects.get(key=key)
    event.save()


def test_play_phase_rotation(event, screen, at):
    _set_phase(event, "play")
    bundle = build_bundle(screen, at(1))
    slides = _slides(bundle)
    assert "house_rules" in slides and "welcome" in slides and "spawn" in slides
    assert "getting_home" not in slides
    # live slides whose integration is not configured are dropped with a warning
    assert "servers" not in slides
    assert any("servers: disabled" in w for w in bundle["warnings"])
    # the schedule slides render from the database without any upstream
    assert "now_next" in slides and "schedule_upcoming" in slides


def test_alternate_and_stacked_expand_differently(event, screen, at):
    _set_phase(event, "play")
    passes = build_bundle(screen, at(1))["passes"]
    rules = [p for p in passes if p["slide"] == "house_rules"]
    assert [p["lang"] for p in rules] == ["hu", "en"]
    welcome = [p for p in passes if p["slide"] == "welcome"]
    assert [p["lang"] for p in welcome] == ["both"]
    assert rules[0]["duration_ms"] == 20000


def test_priority_order_and_screen_lists(event, screen, at):
    _set_phase(event, "play")
    passes = build_bundle(screen, at(1))["passes"]
    first = [p["slide"] for p in passes][:2]
    assert first[0] == "welcome"  # priority 95
    ScreenSlide.objects.create(screen=screen, slide=Slide.objects.get(pk="food"), order=1)
    ScreenSlide.objects.create(screen=screen, slide=Slide.objects.get(pk="voice"), order=0)
    passes = build_bundle(screen, at(1))["passes"]
    assert [p["slide"] for p in passes if p["lang"] == "hu"] == ["voice", "food"]


def test_unresolved_placeholder_drops_the_slide(event, screen, at):
    _set_phase(event, "play")
    event.wifi_ssid = "CHANGE-ME"
    event.save()
    bundle = build_bundle(screen, at(1))
    assert "wifi" not in _slides(bundle)
    assert any(w.startswith("wifi:") for w in bundle["warnings"])


def test_wifi_qr_payload(event, screen, at):
    _set_phase(event, "play")
    passes = build_bundle(screen, at(1))["passes"]
    wifi = next(p for p in passes if p["slide"] == "wifi")
    assert wifi["content"]["link"]["qr_payload"].startswith("WIFI:T:WPA;S:CtrlAltGG;P:")


def test_countdown_only_before_the_start(event, screen, at):
    _set_phase(event, "setup")
    assert "doors_countdown" in _slides(build_bundle(screen, at(-2)))
    bundle = build_bundle(screen, at(1))
    assert "doors_countdown" not in _slides(bundle)


def test_preview_renders_one_pass(event, screen, at):
    bundle = build_bundle(screen, at(1), preview_slide="getting_home", preview_lang="en")
    assert [(p["slide"], p["lang"]) for p in bundle["passes"]] == [("getting_home", "en")]
    assert bundle["preview"] is True


def test_version_changes_with_content(event, screen, at):
    _set_phase(event, "play")
    before = build_bundle(screen, at(1))["version"]
    slide = Slide.objects.get(pk="welcome")
    slide.title_hu = "Más cím"
    slide.save()
    assert build_bundle(screen, at(1))["version"] != before


def test_announcement_precedence_and_takeover(event, screen, at):
    _set_phase(event, "play")
    now = at(1)
    Announcement.objects.create(text_hu="info", text_en="info", level="info", starts_at=now)
    urgent = Announcement.objects.create(
        text_hu="tűz", text_en="fire", level="urgent", takeover=True, starts_at=now
    )
    bundle = build_bundle(screen, now)
    assert bundle["announcement"]["id"] == urgent.pk
    assert bundle["announcement"]["takeover"] is True
    urgent.ends_at = now - timedelta(seconds=1)
    urgent.save()
    assert build_bundle(screen, now)["announcement"]["level"] == "info"


def test_announcement_can_target_one_screen(event, screen, at):
    now = at(1)
    other = Screen.objects.create(slug="tournament", name="Tournament")
    announcement = Announcement.objects.create(text_hu="x", text_en="x", starts_at=now)
    announcement.screens.add(other)
    assert build_bundle(screen, now)["announcement"] is None
    assert build_bundle(other, now)["announcement"]["id"] == announcement.pk


@pytest.mark.django_db
def test_integration_rows_exist_after_migration():
    assert set(Integration.objects.values_list("kind", flat=True)) == {
        "projectile",
        "bracket",
        "streams",
    }
    assert timezone.now() is not None
