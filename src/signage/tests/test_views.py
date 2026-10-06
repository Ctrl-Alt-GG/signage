from pathlib import Path

import pytest
from django.conf import settings

from signage.models import Event, Phase

MANIFEST = Path(settings.FRONTEND_DIST) / ".vite" / "manifest.json"


def test_bundle_and_etag(client, content):
    response = client.get("/api/v1/screens/main/bundle/")
    assert response.status_code == 200
    etag = response["ETag"]
    assert response.json()["screen"]["slug"] == "main"
    assert client.get("/api/v1/screens/main/bundle/", HTTP_IF_NONE_MATCH=etag).status_code == 304


def test_unknown_screen_is_404(client, content):
    assert client.get("/api/v1/screens/nope/bundle/").status_code == 404


def test_preview_query(client, content):
    response = client.get("/api/v1/screens/main/bundle/?preview=food&lang=en")
    passes = response.json()["passes"]
    assert [(p["slide"], p["lang"]) for p in passes] == [("food", "en")]


def test_phase_override_needs_staff(client, admin_client, content):
    event = Event.get_solo()
    event.current_phase = Phase.objects.get(key="setup")
    event.save()
    anonymous = client.get("/api/v1/screens/main/bundle/?phase=late").json()["phase"]["key"]
    staff = admin_client.get("/api/v1/screens/main/bundle/?phase=late").json()["phase"]["key"]
    assert staff == "late"
    assert anonymous == ("late" if settings.DEBUG else "setup")


def test_other_endpoints(client, content):
    assert client.get("/api/v1/schedule/").status_code == 200
    assert client.get("/api/v1/phase/").json()["key"]
    assert client.get("/api/v1/announcements/active/").json() == {"results": []}
    assert client.get("/api/v1/screens/").json()[0]["slug"] == "main"
    background = client.get("/api/v1/display/background.svg")
    assert background.status_code == 200 and background["Content-Type"] == "image/svg+xml"
    assert client.get("/api/v1/display/thumbnails/nope/").status_code == 404
    assert client.get("/health/?format=json").status_code == 200


def test_display_redirects_to_default_screen(client, content):
    response = client.get("/display/")
    assert response.status_code == 302 and response["Location"] == "/display/main/"


@pytest.mark.skipif(not MANIFEST.exists(), reason="frontend not built")
def test_display_page_renders(client, content):
    response = client.get("/display/main/")
    assert response.status_code == 200
    assert b'data-screen="main"' in response.content
    assert b"/static/display/" in response.content
