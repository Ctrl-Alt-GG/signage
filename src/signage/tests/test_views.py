import httpx
import pytest
import respx
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone

from signage.models import Announcement, DisplaySettings, Event, Integration, Phase, Slide


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_bundle(client, content):
    response = client.get("/api/v1/screens/main/bundle/")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    bundle = response.json()
    assert bundle["screen"]["slug"] == "main"
    assert bundle["stage"]["background_url"].startswith("/api/v1/display/background.svg?v=")
    assert "version" not in bundle and "default_screen" not in bundle


def test_bundles_are_shared_for_a_moment_but_each_tells_the_time(client, content, monkeypatch):
    """A room full of screens, or anyone hammering the anonymous API, costs one build."""
    from signage.api import views

    builds = []
    real = views.build_bundle
    monkeypatch.setattr(
        views, "build_bundle", lambda *args, **kwargs: builds.append(1) or real(*args, **kwargs)
    )
    first = client.get("/api/v1/screens/main/bundle/").json()
    second = client.get("/api/v1/screens/main/bundle/").json()
    assert len(builds) == 1
    assert first["passes"] == second["passes"]
    # The screens set their clocks by this, so it is the time of the answer, not of the build.
    assert second["clock"]["now"] > first["clock"]["now"]


def test_unknown_screen_is_404(client, content):
    assert client.get("/api/v1/screens/nope/bundle/").status_code == 404


def test_preview_is_for_staff(client, admin_client, content, settings):
    """A preview shows a slide whether or not it is enabled or in the current phase."""
    settings.DEBUG = False
    Slide.objects.filter(pk="food").update(enabled=False)
    anonymous = client.get("/api/v1/screens/main/bundle/?preview=food&lang=en")
    assert anonymous.status_code == 403
    passes = admin_client.get("/api/v1/screens/main/bundle/?preview=food&lang=en").json()["passes"]
    assert [(p["slide"], p["lang"]) for p in passes] == [("food", "en")]


def test_phase_override_needs_staff(client, admin_client, content, settings):
    settings.DEBUG = False
    event = Event.get_solo()
    event.current_phase = Phase.objects.get(key="setup")
    event.save()
    anonymous = client.get("/api/v1/screens/main/bundle/?phase=late").json()["phase"]["key"]
    staff = admin_client.get("/api/v1/screens/main/bundle/?phase=late").json()["phase"]["key"]
    assert staff == "late"
    assert anonymous == "setup"


def test_other_endpoints(client, content):
    assert client.get("/api/v1/schedule/").status_code == 200
    assert client.get("/api/v1/phase/").json()["key"]
    assert client.get("/api/v1/announcements/active/").json() == {"results": []}
    screens = client.get("/api/v1/screens/").json()
    assert screens[0]["slug"] == "main" and screens[0]["is_default"] is True
    assert client.get("/api/v1/display/thumbnails/nope/").status_code == 404
    assert client.get("/health/?format=json").status_code == 200


def _body(response) -> bytes:
    return b"".join(response.streaming_content)


def test_background_is_the_upload_or_the_bundled_artwork(client, content, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    bundled = client.get("/api/v1/display/background.svg")
    assert bundled.status_code == 200 and bundled["Content-Type"] == "image/svg+xml"
    assert bundled["Cache-Control"] == "no-cache"
    artwork = _body(bundled)

    display = DisplaySettings.get_solo()
    display.background.save("venue.svg", ContentFile(b"<svg>venue</svg>"))
    version = display.background_version
    uploaded = client.get(f"/api/v1/display/background.svg?v={version}")
    assert _body(uploaded) == b"<svg>venue</svg>"
    # The address changes with the artwork, so a copy of this one can be kept.
    assert "max-age=86400" in uploaded["Cache-Control"]

    # A database restored without its uploads must not cost every screen its background.
    (tmp_path / display.background.name).unlink()
    missing = client.get(f"/api/v1/display/background.svg?v={version}")
    assert missing.status_code == 200 and _body(missing) == artwork


def test_files_from_elsewhere_cannot_act_as_pages_of_this_site(client, content):
    """An uploaded SVG opened on its own would otherwise run its script as the admin."""
    response = client.get("/api/v1/display/background.svg")
    assert response["Content-Security-Policy"].startswith("sandbox")
    assert response["X-Content-Type-Options"] == "nosniff"
    response.close()


@respx.mock
def test_thumbnail_is_passed_on_from_streams(client, content, fixture_json):
    row = Integration.objects.get(kind="streams")
    row.enabled = True
    row.base_url = "http://streams-web:8000/api/v1"
    row.save()
    respx.get("http://streams-web:8000/api/v1/streams/").mock(
        return_value=httpx.Response(200, json=fixture_json("streams_list.json"))
    )
    picture = respx.get("http://streams-web:8000/streams/1/thumbnail/").respond(
        200, content=b"jpeg", headers={"content-type": "image/jpeg"}
    )
    url = "/api/v1/display/thumbnails/0192f0a1-0000-7000-8000-000000000001/"
    response = client.get(url + "?v=1")
    assert response.status_code == 200 and response.content == b"jpeg"
    assert response["Content-Type"] == "image/jpeg"
    assert response["Content-Security-Policy"].startswith("sandbox")
    client.get(url + "?v=2")
    assert picture.call_count == 1  # kept for a few seconds, whatever the version says

    # A thumbnail that is not a picture is not passed on.
    cache.clear()
    picture.respond(200, content=b"<html>", headers={"content-type": "text/html"})
    assert client.get(url).status_code == 404


def test_backend_root_goes_to_the_admin(client):
    response = client.get("/")
    assert response.status_code == 302 and response["Location"] == "/admin/"


def test_active_announcement_ids_are_strings(client, content):
    row = Announcement.objects.create(text_hu="szia", text_en="hi", starts_at=timezone.now())
    results = client.get("/api/v1/announcements/active/").json()["results"]
    assert results[0]["id"] == str(row.pk)
    bundle = client.get("/api/v1/screens/main/bundle/").json()
    assert [a["id"] for a in bundle["announcements"]] == [str(row.pk)]
