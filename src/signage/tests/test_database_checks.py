"""The database keeps the invariants that the forms check, whoever writes: a bulk update or a
script gets an error rather than storing what no screen can show."""

from datetime import time, timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from signage.concurrency import row_version
from signage.models import (
    Announcement,
    DisplaySettings,
    Event,
    Integration,
    Phase,
    ScheduleEntry,
    Screen,
    Slide,
    SlideItem,
)


@pytest.mark.parametrize(
    ("write", "constraint"),
    [
        (lambda: Event.objects.update(ends_at=Event.get_solo().starts_at), "event_ends_after"),
        (
            lambda: DisplaySettings.objects.filter(pk=DisplaySettings.get_solo().pk).update(
                safe_x=1000, safe_width=1728
            ),
            "display_safe",
        ),
        (lambda: Integration.objects.update(connect_timeout=4, read_timeout=7), "upstream_time"),
        (lambda: Slide.objects.update(duration_seconds=200), "slide_timing"),
        (lambda: Screen.objects.update(refresh_seconds=1), "screen_refresh"),
        (lambda: Phase.objects.update(day_offset=9), "phase_day_offset"),
        (lambda: ScheduleEntry.objects.update(day_offset=-1), "schedule_day_offset"),
        (lambda: SlideItem.objects.update(column=3), "slideitem_column"),
    ],
)
def test_a_write_that_breaks_an_invariant_is_refused(content, write, constraint):
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        write()


def test_an_announcement_cannot_end_before_it_starts(content):
    now = timezone.now()
    announcement = Announcement.objects.create(text_hu="x", text_en="x", starts_at=now)
    refused = pytest.raises(IntegrityError, match="announcement_ends_after_start")
    with refused, transaction.atomic():
        Announcement.objects.filter(pk=announcement.pk).update(ends_at=now)


def test_a_form_names_the_problem_once_on_its_field(admin_client, content):
    phase = Phase.objects.get(key="play")

    response = admin_client.post(
        reverse("admin:signage_phase_change", args=[phase.pk]),
        {
            "row_version": row_version(phase),
            "key": phase.key,
            "name_hu": phase.name_hu,
            "name_en": phase.name_en,
            "starts": phase.starts.strftime("%H:%M"),
            "day_offset": "9",
            "order": str(phase.order),
        },
    )
    page = response.content.decode()
    assert response.status_code == 200
    assert page.count("Ensure this value is less than or equal to 7.") == 1
    assert "A day from 0 to 7." not in page


def test_ending_announcements_now_turns_off_those_that_have_not_started(admin_client, content):
    now = timezone.now()
    running = Announcement.objects.create(
        text_hu="most", text_en="now", starts_at=now - timedelta(minutes=5)
    )
    later = Announcement.objects.create(
        text_hu="később", text_en="later", starts_at=now + timedelta(hours=1)
    )
    admin_client.post(
        reverse("admin:signage_announcement_changelist"),
        {"action": "end_now", "_selected_action": [running.pk, later.pk]},
    )
    running.refresh_from_db()
    later.refresh_from_db()
    assert running.ends_at is not None and running.ends_at <= timezone.now()
    assert later.enabled is False and later.ends_at is None


@pytest.mark.django_db(transaction=True)
def test_schedule_rows_from_before_keys_get_the_keys_of_their_slots(settings, tmp_path):
    """The keys come from the migration itself, whatever the content directory says now."""
    settings.SIGNAGE_CONTENT_DIR = tmp_path
    before = [("signage", "0002_seed")]
    after = [("signage", "0003_origin_and_schedule_keys")]
    executor = MigrationExecutor(connection)
    executor.migrate(before)
    try:
        entry = executor.loader.project_state(before).apps.get_model("signage", "ScheduleEntry")
        for title in ("Kezdés egy kis építkezéssel", "Saját program", "Saját program"):
            entry.objects.create(
                time=time(15, 30) if title.startswith("Kezdés") else time(21, 0),
                day_offset=0,
                title_hu=title,
                title_en=title,
            )
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        keyed = executor.loader.project_state(after).apps.get_model("signage", "ScheduleEntry")
        assert sorted(keyed.objects.values_list("key", flat=True)) == [
            "d0-2100-sajat-program",
            "d0-2100-sajat-program-2",
            "minecraft-start",
        ]
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
