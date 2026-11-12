from datetime import timedelta

import httpx
import pytest
import respx
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone

from signage.models import (
    Announcement,
    DisplaySettings,
    Event,
    Integration,
    Phase,
    Screen,
    ScreenSlide,
    Slide,
)
from signage.rendering.bundle import build_bundle, stamp


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
    assert "house_rules" in slides and "welcome" in slides and "start_here" in slides
    assert "getting_home" not in slides
    # live slides whose integration is not configured are dropped with a warning
    assert "servers" not in slides
    assert any("servers: disabled" in w for w in bundle["warnings"])
    # the schedule slides render from the database without any upstream
    assert "now_next" in slides and "schedule_upcoming" in slides


def test_alternate_and_stacked_expand_differently(event, screen, at):
    _set_phase(event, "play")
    rules_slide = Slide.objects.get(pk="house_rules")
    rules_slide.bilingual_mode = Slide.BilingualMode.ALTERNATE
    rules_slide.save()
    passes = build_bundle(screen, at(1))["passes"]
    rules = [p for p in passes if p["slide"] == "house_rules"]
    assert [p["lang"] for p in rules] == ["hu", "en"]
    welcome = [p for p in passes if p["slide"] == "welcome"]
    assert [p["lang"] for p in welcome] == ["both"]
    assert rules[0]["duration_ms"] == 18000


def test_priority_order_and_screen_lists(event, screen, at):
    _set_phase(event, "play")
    passes = build_bundle(screen, at(1))["passes"]
    first = [p["slide"] for p in passes][:2]
    assert first[0] == "welcome"  # priority 95
    ScreenSlide.objects.create(screen=screen, slide=Slide.objects.get(pk="food"), order=1)
    ScreenSlide.objects.create(screen=screen, slide=Slide.objects.get(pk="voice"), order=0)
    passes = build_bundle(screen, at(1))["passes"]
    assert [p["slide"] for p in passes] == ["voice", "food"]


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


@pytest.mark.parametrize(
    ("password", "encoded"),
    [
        ("ab  cd", "ab  cd"),
        (" abcd ", " abcd "),
        ('a:{b};c\\d"', 'a\\:{b}\\;c\\\\d\\"'),
        ("x" * 128, "x" * 128),
    ],
)
def test_wifi_credentials_survive_admin_save_and_match_the_qr(event, screen, at, password, encoded):
    from signage.admin import EventForm

    ssid = " LAN  {main}:1 "
    form = EventForm({"wifi_ssid": ssid, "wifi_password": password}, instance=event)
    assert form.is_valid(), form.errors
    form.save()
    event.refresh_from_db()
    assert event.wifi_ssid == ssid and event.wifi_password == password
    _set_phase(event, "play")
    wifi = next(p for p in build_bundle(screen, at(1))["passes"] if p["slide"] == "wifi")
    assert wifi["content"]["wifi_credentials"] == {"ssid": ssid, "password": password}
    assert wifi["content"]["link"]["qr_payload"] == (
        f"WIFI:T:WPA;S: LAN  {{main}}\\:1 ;P:{encoded};;"
    )


def test_open_wifi_needs_no_password(event, screen, at):
    event.wifi_security = "nopass"
    event.wifi_password = ""
    event.save()
    _set_phase(event, "play")
    wifi = next(p for p in build_bundle(screen, at(1))["passes"] if p["slide"] == "wifi")
    assert wifi["content"]["wifi_credentials"] == {"ssid": "CtrlAltGG", "password": None}
    assert wifi["content"]["link"]["qr_payload"] == "WIFI:T:nopass;S:CtrlAltGG;;"


def test_every_live_match_gets_a_consecutive_pass_including_in_previews(
    event, screen, at, monkeypatch
):
    matches = [{"id": i, "team1": f"ALPHA-{i}", "team2": f"BETA-{i}"} for i in range(1, 5)]
    monkeypatch.setattr(
        "signage.rendering.bundle.live_data",
        lambda *args: {"live": matches, "upcoming": [], "results": [], "stale": False},
    )
    for lang in ("hu", "en", "both"):
        passes = build_bundle(screen, at(1), preview_slide="tournament_live", preview_lang=lang)[
            "passes"
        ]
        assert [p["key"] for p in passes] == [
            f"tournament_live:{lang}:page-1",
            f"tournament_live:{lang}:page-2",
        ]
        assert [p["lang"] for p in passes] == [lang, lang]
        assert [[m["id"] for m in p["live"]["live"]] for p in passes] == [[1, 2], [3, 4]]
        assert [p["live"]["live_page"] for p in passes] == [
            {"number": 1, "count": 2, "first": 1, "last": 2, "total": 4},
            {"number": 2, "count": 2, "first": 3, "last": 4, "total": 4},
        ]
        assert all(p["duration_ms"] == 20000 for p in passes)


def test_countdown_only_before_the_start(event, screen, at):
    _set_phase(event, "setup")
    assert "doors_countdown" in _slides(build_bundle(screen, at(-2)))
    bundle = build_bundle(screen, at(1))
    assert "doors_countdown" not in _slides(bundle)


def test_preview_renders_one_pass(event, screen, at):
    bundle = build_bundle(screen, at(1), preview_slide="getting_home", preview_lang="en")
    assert [(p["slide"], p["lang"]) for p in bundle["passes"]] == [("getting_home", "en")]
    assert bundle["preview"] is True


def test_stage_follows_the_display_settings(event, screen, at):
    _set_phase(event, "play")
    bundle = build_bundle(screen, at(1))
    assert bundle["stage"]["safe"] == {"x": 96, "y": 204, "width": 1728, "height": 564}
    display = DisplaySettings.get_solo()
    display.safe_x = 120
    display.safe_width = 1700
    display.save()
    assert build_bundle(screen, at(1))["stage"]["safe"]["x"] == 120


def test_background_address_changes_with_the_artwork(event, screen, at, settings, tmp_path):
    """A running screen only fetches the background again when its address changes."""
    settings.MEDIA_ROOT = tmp_path
    bundled = build_bundle(screen, at(1))["stage"]["background_url"]
    assert bundled == "/api/v1/display/background.svg?v=bundled"

    display = DisplaySettings.get_solo()
    display.background.save("venue.svg", ContentFile(b"<svg/>"))
    first = build_bundle(screen, at(1))["stage"]["background_url"]
    display.background.save("venue.svg", ContentFile(b"<svg></svg>"))
    second = build_bundle(screen, at(1))["stage"]["background_url"]
    assert len({bundled, first, second}) == 3


def test_announcements_are_listed_most_important_first(event, screen, at):
    _set_phase(event, "play")
    now = at(1)
    info = Announcement.objects.create(text_hu="info", text_en="info", level="info", starts_at=now)
    warning = Announcement.objects.create(
        text_hu="áram", text_en="power", level="warning", starts_at=now
    )
    urgent = Announcement.objects.create(
        text_hu="tűz", text_en="fire", level="urgent", takeover=True, starts_at=now
    )
    announcements = build_bundle(screen, now)["announcements"]
    # All of them are there: a second announcement no longer waits for the first to end.
    assert [a["id"] for a in announcements] == [str(urgent.pk), str(warning.pk), str(info.pk)]
    assert announcements[0]["takeover"] is True

    urgent.ends_at = now - timedelta(seconds=1)
    urgent.save()
    assert [a["level"] for a in build_bundle(screen, now)["announcements"]] == ["warning", "info"]


def test_ended_and_future_announcements_are_not_loaded(
    event, screen, at, django_assert_num_queries
):
    now = at(1)
    for index in range(30):
        Announcement.objects.create(
            text_hu=f"régi {index}",
            text_en=f"old {index}",
            starts_at=now - timedelta(hours=2),
            ends_at=now - timedelta(hours=1),
        )
    Announcement.objects.create(text_hu="később", text_en="later", starts_at=at(2))
    current = Announcement.objects.create(text_hu="most", text_en="now", starts_at=now)
    from signage.rendering.bundle import active_announcements

    # One query for the announcements and one for their screens, however many have ended.
    with django_assert_num_queries(2):
        assert active_announcements(now) == [current]


def test_announcement_can_target_one_screen(event, screen, at):
    now = at(1)
    other = Screen.objects.create(slug="tournament", name="Tournament")
    announcement = Announcement.objects.create(text_hu="x", text_en="x", starts_at=now)
    announcement.screens.add(other)
    assert build_bundle(screen, now)["announcements"] == []
    assert [a["id"] for a in build_bundle(other, now)["announcements"]] == [str(announcement.pk)]


def test_phase_and_screen_checks_use_what_was_loaded(
    event, screen, at, django_assert_max_num_queries
):
    """The rotation is built on every poll of every screen. Its cost does not grow with the
    number of slides."""
    _set_phase(event, "play")
    now = at(1)
    assert len(build_bundle(screen, now)["passes"]) > 10
    with django_assert_max_num_queries(16):
        build_bundle(screen, now)


@respx.mock
def test_stream_thumbnails_get_a_new_address_with_every_refresh(
    event, screen, at, settings, fixture_json
):
    """Every slide stays loaded on a screen, so a thumbnail at a fixed address would show
    its first frame all day."""
    cache.clear()
    _set_phase(event, "play")
    row = Integration.objects.get(kind="streams")
    row.enabled = True
    row.base_url = "https://streams.example/api/v1"
    row.save()
    respx.get("https://streams.example/api/v1/streams/").mock(
        return_value=httpx.Response(200, json=fixture_json("streams_list.json"))
    )
    ScreenSlide.objects.create(screen=screen, slide=Slide.objects.get(pk="streams_live"), order=0)

    def thumbnails(now):
        [streams] = [p for p in build_bundle(screen, now)["passes"] if p["slide"] == "streams_live"]
        return [channel["thumbnail_url"] for channel in streams["live"]["live"]]

    period = timedelta(seconds=settings.SIGNAGE_THUMBNAIL_CACHE_SECONDS)
    first, later = thumbnails(at(1)), thumbnails(at(1) + period)
    assert first[0].startswith(
        "/api/v1/display/thumbnails/0192f0a1-0000-7000-8000-000000000001/?v="
    )
    assert first != later
    cache.clear()


def test_stamp_gives_every_answer_its_own_time(event, screen, at):
    bundle = build_bundle(screen, at(1))
    later = stamp(bundle, at(1) + timedelta(seconds=30))
    assert later["passes"] is bundle["passes"]
    assert later["clock"]["now"] != bundle["clock"]["now"]
    assert (
        later["clock"]["now"].endswith("+02:00") and later["clock"]["timezone"] == "Europe/Budapest"
    )


@pytest.mark.django_db
def test_integration_rows_exist_after_migration():
    assert set(Integration.objects.values_list("kind", flat=True)) == {
        "projectile",
        "bracket",
        "streams",
    }
    assert timezone.now() is not None
