from datetime import time

from django.conf import settings

from signage.content.loader import load_all, load_schedule, read_yaml
from signage.models import (
    AnnouncementTemplate,
    Game,
    Origin,
    Phase,
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
