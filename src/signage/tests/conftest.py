import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings

from signage.content.loader import load_all
from signage.models import Event, Origin, Screen

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_parallel_suffix, tmp_path_factory):
    """With SQLite, a test database in a file rather than in memory. Django never closes a
    connection to an in-memory database, as that would delete it, so the one the health
    check opens in a thread of its own would be left for the garbage collector. With
    PostgreSQL (DATABASE_URL), Django creates a test database next to the configured one."""
    if settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
        settings.DATABASES["default"]["TEST"] = {
            **settings.DATABASES["default"].get("TEST", {}),
            "NAME": str(tmp_path_factory.mktemp("database") / "signage.sqlite3"),
        }


@pytest.fixture
def fixture_json():
    def load(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return load


@pytest.fixture
def content(db):
    """The real content/ directory loaded into the test database, with the organizer-only
    values filled in, as in the admin, so no slide is dropped for an unresolved placeholder."""
    report = load_all(settings.SIGNAGE_CONTENT_DIR)
    event = Event.get_solo()
    event.wifi_ssid = "CtrlAltGG"
    event.wifi_password = "only-for-the-tests"
    event.assembly_point_hu = "Az épület előtt"
    event.assembly_point_en = "In front of the building"
    event.origin = Origin.ADMIN
    event.save()
    return report


@pytest.fixture
def event(content):
    return Event.get_solo()


@pytest.fixture
def screen(content):
    return Screen.objects.get(slug="main")


@pytest.fixture
def at(event):
    """Return an aware datetime `hours` after the event start (negative values allowed)."""

    def shift(hours: float):
        return event.starts_at + timedelta(hours=hours)

    return shift
