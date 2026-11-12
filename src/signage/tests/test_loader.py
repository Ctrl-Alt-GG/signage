from datetime import time

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError

from signage.content.loader import (
    load_all,
    load_announcements,
    load_schedule,
    load_slides,
    read_yaml,
)
from signage.models import (
    AnnouncementTemplate,
    Event,
    Game,
    Origin,
    Phase,
    RemovedSeed,
    ScheduleEntry,
    Slide,
    SlideItem,
)


def test_counts_match_the_yaml(content):
    assert Slide.objects.count() == 27
    assert ScheduleEntry.objects.count() == 17
    assert Phase.objects.count() == 7
    assert Game.objects.count() == 27
    assert AnnouncementTemplate.objects.count() == 13
    assert SlideItem.objects.filter(slide__key="power_network", column=2).count() == 3
    assert Slide.objects.get(pk="start_here").all_phases is True
    assert Slide.objects.get(pk="welcome").phases.count() == 2


def test_second_run_creates_nothing(content):
    report = load_all(settings.SIGNAGE_CONTENT_DIR)
    assert report.created == 0
    assert Slide.objects.count() == 27
    assert ScheduleEntry.objects.count() == 17


def test_admin_edits_survive_unless_overwritten(content):
    slide = Slide.objects.get(pk="welcome")
    slide.title_hu = "Szerkesztve"
    slide.origin = Origin.ADMIN
    slide.save()
    report = load_all(settings.SIGNAGE_CONTENT_DIR, only={"slides"})
    assert "slide welcome" in report.skipped
    assert Slide.objects.get(pk="welcome").title_hu == "Szerkesztve"
    load_all(settings.SIGNAGE_CONTENT_DIR, only={"slides"}, overwrite=True)
    assert Slide.objects.get(pk="welcome").title_hu == "Üdv a bulin, nerdek!"


def test_every_seeded_table_keeps_admin_edits_unless_overwritten(content):
    entry = ScheduleEntry.objects.get(key="dinner-break")
    entry.title_en = "Food time"
    entry.origin = Origin.ADMIN
    entry.save()
    game = Game.objects.get(slug="cs2")
    game.short = "CS"
    game.origin = Origin.ADMIN
    game.save()
    phase = Phase.objects.get(key="setup")
    phase.day_offset = 5
    phase.origin = Origin.ADMIN
    phase.save()
    template = AnnouncementTemplate.objects.first()
    template.text_en = "Edited"
    template.origin = Origin.ADMIN
    template.save()

    report = load_all(settings.SIGNAGE_CONTENT_DIR)
    assert {"schedule dinner-break", "game cs2", "phase setup", f"template {template.key}"} <= set(
        report.skipped
    )
    assert ScheduleEntry.objects.get(key="dinner-break").title_en == "Food time"
    assert Game.objects.get(slug="cs2").short == "CS"
    assert Phase.objects.get(key="setup").day_offset == 5
    assert AnnouncementTemplate.objects.get(pk=template.pk).text_en == "Edited"

    load_all(settings.SIGNAGE_CONTENT_DIR, overwrite=True)
    assert ScheduleEntry.objects.get(key="dinner-break").title_en == "Dinner break"
    assert Game.objects.get(slug="cs2").origin == Origin.SEED
    assert Game.objects.get(slug="cs2").short != "CS"
    assert Phase.objects.get(key="setup").day_offset == 0
    assert AnnouncementTemplate.objects.get(pk=template.pk).text_en != "Edited"


def test_schedule_rows_follow_their_key_not_their_title(content):
    data = read_yaml(settings.SIGNAGE_CONTENT_DIR / "schedule.yaml")
    first = data["entries"][0]
    first["title"]["hu"] = "Új cím"
    first["title"]["en"] = "New title"
    load_schedule(data)
    assert ScheduleEntry.objects.count() == 17
    assert ScheduleEntry.objects.get(key=first["key"]).title_hu == "Új cím"


def test_rows_created_in_the_admin_get_a_generated_key(db):
    entry = ScheduleEntry.objects.create(time=time(12, 0), title_hu="Ebéd", title_en="Lunch")
    assert entry.key.startswith("entry-")
    other = ScheduleEntry.objects.create(time=time(13, 0), title_hu="Kávé", title_en="Coffee")
    assert other.key != entry.key


def test_a_row_deleted_in_the_admin_stays_deleted(content):
    """The import runs on every start of the stack. It must not undo an organizer's
    decision to take a slide off the screens for good."""
    slide = Slide.objects.get(pk="welcome")
    RemovedSeed.remember(slide)
    slide.delete()
    game = Game.objects.get(slug="cs2")
    RemovedSeed.remember(game)
    game.delete()

    report = load_all(settings.SIGNAGE_CONTENT_DIR)
    assert not Slide.objects.filter(pk="welcome").exists()
    assert not Game.objects.filter(slug="cs2").exists()
    assert {"slide welcome (deleted in the admin)", "game cs2 (deleted in the admin)"} <= set(
        report.skipped
    )

    # Overwriting is how an organizer asks for the YAML again, deleted rows included.
    load_all(settings.SIGNAGE_CONTENT_DIR, overwrite=True)
    assert Slide.objects.filter(pk="welcome").exists()
    assert Game.objects.filter(slug="cs2").exists()
    assert not RemovedSeed.objects.exists()


def test_a_deleted_phase_does_not_break_importing_the_slides_it_used_to_show(content):
    phase = Phase.objects.get(key="arrival")
    RemovedSeed.remember(phase)
    phase.delete()
    report = load_all(settings.SIGNAGE_CONTENT_DIR)
    assert not Phase.objects.filter(key="arrival").exists()
    assert Slide.objects.get(pk="welcome").phases.count() == 1
    assert any(
        "phases deleted in the admin are omitted: arrival" in text for text in report.warnings
    )
    load_all(settings.SIGNAGE_CONTENT_DIR, overwrite=True)
    assert Slide.objects.get(pk="welcome").phases.count() == 2


def test_rows_that_left_the_yaml_are_removed_unless_an_organizer_made_them_theirs(content):
    data = read_yaml(settings.SIGNAGE_CONTENT_DIR / "slides.yaml")
    left, edited = data["slides"].pop(), data["slides"].pop()
    Slide.objects.filter(pk=edited["id"]).update(origin=Origin.ADMIN)
    Slide.objects.create(
        key="made_here", layout="hero", title_hu="Itt készült", origin=Origin.ADMIN
    )

    report = load_slides(data, prune=True)
    assert report.removed == [f"slide {left['id']}"]
    assert not Slide.objects.filter(pk=left["id"]).exists()
    assert Slide.objects.filter(pk__in=[edited["id"], "made_here"]).count() == 2
    assert "removed" in report.summary()


def test_a_partial_file_removes_nothing_unless_asked(content):
    data = read_yaml(settings.SIGNAGE_CONTENT_DIR / "schedule.yaml")
    data["entries"] = data["entries"][:1]
    report = load_schedule(data)
    assert report.removed == [] and ScheduleEntry.objects.count() == 17


def test_removing_the_current_phase_falls_back_to_the_first(content):
    event = Event.get_solo()
    event.current_phase = Phase.objects.get(key="late")
    event.save()
    data = read_yaml(settings.SIGNAGE_CONTENT_DIR / "event.yaml")
    data["phases"] = [phase for phase in data["phases"] if phase["key"] != "late"]
    from signage.content.loader import load_event

    load_event(data, prune=True)
    assert not Phase.objects.filter(key="late").exists()
    assert Event.get_solo().current_phase.key == "setup"


def test_text_that_does_not_fit_is_named_and_nothing_is_saved(content):
    data = read_yaml(settings.SIGNAGE_CONTENT_DIR / "announcements.yaml")
    data["templates"][0]["text"]["en"] = "Edited"
    data["templates"][1]["text"]["hu"] = "x" * 301
    with pytest.raises(ValidationError, match="text_hu"):
        load_announcements(data)
    # The first template was fine, and still is as it was: an import is all or nothing.
    first = AnnouncementTemplate.objects.get(key=data["templates"][0]["key"])
    assert first.text_en != "Edited"


def test_an_unknown_placeholder_in_an_item_is_refused(content):
    data = read_yaml(settings.SIGNAGE_CONTENT_DIR / "slides.yaml")
    slide = next(slide for slide in data["slides"] if slide.get("items"))
    slide["items"][0]["hu"] = "Csatlakozz: {wifi_name}"
    with pytest.raises(ValidationError, match="wifi_name"):
        load_slides(data)
