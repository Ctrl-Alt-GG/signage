import re
from datetime import timedelta

import pytest
from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.utils import timezone

from signage.models import (
    Announcement,
    AnnouncementTemplate,
    DisplaySettings,
    Event,
    Integration,
    Slide,
)

FROM_TEMPLATE = "/admin/signage/announcement/from-template/"


def _template(key: str) -> AnnouncementTemplate:
    return AnnouncementTemplate.objects.get(key=key)


def _fields(page: str) -> set[str]:
    return set(re.findall(r'name="(ph_[a-z0-9_]+)"', page))


def test_choosing_a_template_shows_an_empty_form_without_errors(admin_client, content):
    listing = admin_client.get(FROM_TEMPLATE).content.decode()
    template = _template("match_call")
    assert f'href="?template={template.pk}"' in listing

    page = admin_client.get(f"{FROM_TEMPLATE}?template={template.pk}").content.decode()
    assert _fields(page) == {"ph_team_a", "ph_team_b", "ph_minutes"}
    # Nothing has been typed yet, so nothing is wrong yet.
    assert "errorlist" not in page and "This field is required" not in page


def test_what_the_event_knows_is_filled_in_and_not_asked_for(admin_client, content):
    """Under pressure nobody should have to type the assembly point."""
    template = _template("evacuate")
    page = admin_client.get(f"{FROM_TEMPLATE}?template={template.pk}").content.decode()
    assert _fields(page) == set()
    assert "Az épület előtt / In front of the building" in page

    response = admin_client.post(
        FROM_TEMPLATE, {"template": template.pk, "duration_minutes": 0, "publish": "1"}
    )
    assert response.status_code == 302
    announcement = Announcement.objects.get()
    assert announcement.text_hu.endswith("Gyülekező: Az épület előtt.")
    assert announcement.text_en.endswith("Assembly point: In front of the building.")
    assert announcement.takeover and announcement.level == "urgent" and announcement.ends_at is None


def test_a_value_the_event_lacks_is_asked_for(admin_client, content):
    event = Event.get_solo()
    event.assembly_point_hu = "CHANGE-ME"
    event.save()
    template = _template("evacuate")
    page = admin_client.get(f"{FROM_TEMPLATE}?template={template.pk}").content.decode()
    assert _fields(page) == {"ph_assembly_point"}


def test_preview_shows_the_text_before_anything_is_published(admin_client, content):
    template = _template("match_call")
    values = {"ph_team_a": "Eco Round", "ph_team_b": "Clutch Kings", "ph_minutes": "10"}
    response = admin_client.post(
        FROM_TEMPLATE,
        {"template": template.pk, "duration_minutes": 10, "preview": "1", **values},
    )
    page = response.content.decode()
    assert response.status_code == 200
    assert "CS2: Eco Round vs Clutch Kings 10 perc múlva kezdődik." in page
    assert "characters" in page
    assert not Announcement.objects.exists()

    before = timezone.now()
    response = admin_client.post(
        FROM_TEMPLATE,
        {"template": template.pk, "duration_minutes": 10, "publish": "1", **values},
    )
    assert response.status_code == 302
    announcement = Announcement.objects.get()
    assert (
        announcement.text_en
        == "CS2: Eco Round vs Clutch Kings starts in 10 minutes. Get to your PCs!"
    )
    assert announcement.created_by.is_superuser
    assert timedelta(minutes=9) < announcement.ends_at - before < timedelta(minutes=11)


def test_a_text_that_would_not_fit_is_reported_on_the_form(admin_client, content):
    """Template text plus what is typed can pass the column's length, which used to be an
    error page on PostgreSQL."""
    template = _template("match_call")
    response = admin_client.post(
        FROM_TEMPLATE,
        {
            "template": template.pk,
            "duration_minutes": 10,
            "publish": "1",
            "ph_team_a": "x" * 120,
            "ph_team_b": "y" * 120,
            "ph_minutes": "z" * 120,
        },
    )
    page = response.content.decode()
    assert response.status_code == 200
    assert "at most 300 characters" in page
    assert not Announcement.objects.exists()


def test_odd_templates_and_addresses_do_not_crash(admin_client, content):
    template = AnnouncementTemplate.objects.create(
        key="odd",
        text_hu="{team1} {} {0} {Nagy} 100% {team1}",
        text_en="{team1} {} {0} {Nagy} 100% {team1}",
    )
    page = admin_client.get(f"{FROM_TEMPLATE}?template={template.pk}").content.decode()
    assert _fields(page) == {"ph_team1"}
    response = admin_client.post(
        FROM_TEMPLATE,
        {"template": template.pk, "duration_minutes": 10, "publish": "1", "ph_team1": "{0}"},
    )
    assert response.status_code == 302
    assert Announcement.objects.get().text_hu == "{0} {} {0} {Nagy} 100% {0}"

    for address in (
        "?template=abc",
        "?template=999999",
        "?template=",
        "?template=²",
        "?template=" + "9" * 4500,
    ):
        assert admin_client.get(FROM_TEMPLATE + address).status_code == 200


def test_a_long_bar_announcement_gets_a_warning(admin_client, content):
    response = admin_client.post(
        "/admin/signage/announcement/add/",
        {
            "text_hu": "x" * 200,
            "text_en": "short",
            "level": "info",
            "enabled": "on",
            "starts_at_0": "2026-10-03",
            "starts_at_1": "18:00:00",
        },
        follow=True,
    )
    assert Announcement.objects.count() == 1
    assert "Long for the bar" in response.content.decode()


# ---------------------------------------------------------------- integrations


@pytest.fixture
def streams(db):
    cache.clear()
    row = Integration.objects.get(kind="streams")
    row.enabled = True
    row.base_url = "https://streams.example/api/v1"
    row.auth_type = Integration.Auth.BASIC
    row.username = "signage"
    row.password = "s3cret-upstream-password"
    row.token = "t0ken-value"
    row.save()
    return row


def _integration_form(row: Integration, **changes) -> dict:
    data = {
        "enabled": "on",
        "base_url": row.base_url,
        "auth_type": row.auth_type,
        "username": row.username,
        "password": "",
        "token": "",
        "header_name": row.header_name,
        "verify_tls": "on",
        "ca_bundle": "",
        "connect_timeout": "2.0",
        "read_timeout": "4.0",
        "cache_seconds": "15",
        "tournament_id": "",
    }
    data.update(changes)
    return data


def test_stored_secrets_are_never_written_into_the_page(admin_client, streams):
    page = admin_client.get(f"/admin/signage/integration/{streams.pk}/change/").content.decode()
    assert "s3cret-upstream-password" not in page and "t0ken-value" not in page
    assert "A value is stored" in page
    # The browser must not offer the organizer's own login for these fields.
    assert page.count('autocomplete="new-password"') == 2


def test_saving_without_typing_a_secret_keeps_it(admin_client, streams):
    url = f"/admin/signage/integration/{streams.pk}/change/"
    response = admin_client.post(url, _integration_form(streams, cache_seconds="30"))
    assert response.status_code == 302
    streams.refresh_from_db()
    assert streams.cache_seconds == 30
    assert streams.password == "s3cret-upstream-password" and streams.token == "t0ken-value"

    admin_client.post(url, _integration_form(streams, password="a-new-password"))
    streams.refresh_from_db()
    assert streams.password == "a-new-password"


def test_someone_who_may_only_look_does_not_see_the_secrets(client, streams):
    user = User.objects.create_user("viewer", password="x", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_integration"))
    client.force_login(user)
    page = client.get(f"/admin/signage/integration/{streams.pk}/change/").content.decode()
    assert "https://streams.example/api/v1" in page
    assert "s3cret-upstream-password" not in page and "t0ken-value" not in page


def test_bracket_needs_its_tournament_and_an_internal_address_is_accepted(admin_client, db):
    bracket = Integration.objects.get(kind="bracket")
    url = f"/admin/signage/integration/{bracket.pk}/change/"
    form = _integration_form(bracket, base_url="http://bracket-backend:8400/api", auth_type="none")
    response = admin_client.post(url, form)
    assert response.status_code == 200
    assert "Choose the tournament" in response.content.decode()

    response = admin_client.post(url, {**form, "tournament_id": "12"})
    assert response.status_code == 302
    bracket.refresh_from_db()
    assert bracket.is_configured and bracket.tournament_id == 12

    response = admin_client.post(url, {**form, "tournament_id": "12", "read_timeout": "0"})
    assert response.status_code == 200 and not response.context["adminform"].form.is_valid()


# ---------------------------------------------------------------- slides and display


def _slide_form(slide: Slide, items: int) -> dict:
    data = {
        "layout": slide.layout,
        "source": slide.source,
        "enabled": "on",
        "all_phases": "on",
        "duration_seconds": "15",
        "bilingual_mode": slide.bilingual_mode,
        "priority": "50",
        "order": "0",
        "title_hu": slide.title_hu,
        "title_en": slide.title_en,
        "labels": "{}",
        "items-TOTAL_FORMS": str(items),
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "1000",
    }
    for index in range(items):
        data[f"items-{index}-column"] = "1"
        data[f"items-{index}-order"] = str(index)
        data[f"items-{index}-text_hu"] = f"pont {index}"
        data[f"items-{index}-text_en"] = f"item {index}"
    return data


def test_a_seventh_item_is_refused_instead_of_dropped_on_the_screen(admin_client, content):
    slide = Slide.objects.get(pk="house_rules")
    slide.items.all().delete()
    url = "/admin/signage/slide/house_rules/change/"
    response = admin_client.post(url, _slide_form(slide, 7))
    assert response.status_code == 200
    assert "at most 6 items" in response.content.decode()
    assert slide.items.count() == 0

    assert admin_client.post(url, _slide_form(slide, 6)).status_code == 302
    assert slide.items.count() == 6


def test_a_split_column_refuses_a_fifth_item_that_the_layout_would_drop(admin_client, content):
    slide = Slide.objects.get(pk="power_network")
    slide.items.all().delete()
    form = _slide_form(slide, 5)
    form.update(
        column1_title_hu=slide.column1_title_hu,
        column1_title_en=slide.column1_title_en,
        column2_title_hu=slide.column2_title_hu,
        column2_title_en=slide.column2_title_en,
    )
    response = admin_client.post("/admin/signage/slide/power_network/change/", form)
    assert response.status_code == 200
    assert "at most 4 items" in response.content.decode()
    assert slide.items.count() == 0


def test_an_unknown_placeholder_is_reported_when_the_slide_is_saved(admin_client, content):
    slide = Slide.objects.get(pk="house_rules")
    slide.items.all().delete()
    url = "/admin/signage/slide/house_rules/change/"
    response = admin_client.post(url, {**_slide_form(slide, 0), "title_hu": "Wi-Fi: {wifi_name}"})
    assert response.status_code == 200
    assert "Unknown placeholder: {wifi_name}" in response.content.decode()
    # Braces that are no placeholder are just text.
    response = admin_client.post(url, {**_slide_form(slide, 0), "title_hu": "Szabályok { }"})
    assert response.status_code == 302


def test_stage_geometry_that_would_break_the_display_is_refused(admin_client, db):
    display = DisplaySettings.get_solo()
    form = {
        "default_screen_slug": "main",
        "stage_width": "1920",
        "stage_height": "1080",
        "safe_x": "96",
        "safe_y": "204",
        "safe_width": "1728",
        "safe_height": "564",
    }
    url = "/admin/signage/displaysettings/"
    for change in ({"stage_width": "0"}, {"safe_height": "0"}, {"safe_width": "1900"}):
        response = admin_client.post(url, {**form, **change})
        assert response.status_code == 200, change
    assert admin_client.post(url, form).status_code == 302
    display.refresh_from_db()
    assert display.stage_width == 1920


def test_overview_lists_every_announcement_and_integration_problems(admin_client, content):
    now = timezone.now()
    Announcement.objects.create(text_hu="első", text_en="first", starts_at=now)
    Announcement.objects.create(text_hu="második", text_en="second", starts_at=now, level="warning")
    page = admin_client.get("/admin/signage/overview/").content.decode()
    assert "első" in page and "második" in page
    assert "Problem" in page


def test_schedule_list_sorts_by_when_things_happen(admin_client, content):
    """An entry after midnight belongs after the evening, not before the afternoon."""
    response = admin_client.get("/admin/signage/scheduleentry/?o=1")
    rows = list(response.context["cl"].result_list)
    moments = [(row.day_offset, row.time) for row in rows]
    assert moments == sorted(moments)
    assert rows[-1].day_offset == 1
