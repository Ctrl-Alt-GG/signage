from django.conf import settings

from signage.content.loader import load_all
from signage.models import AnnouncementTemplate, Game, Phase, ScheduleEntry, Slide, SlideItem


def test_counts_match_the_yaml(content):
    assert Slide.objects.count() == 25
    assert ScheduleEntry.objects.count() == 17
    assert Phase.objects.count() == 7
    assert Game.objects.count() == 27
    assert AnnouncementTemplate.objects.count() == 13
    assert SlideItem.objects.filter(slide__key="power_network", column=2).count() == 4
    assert Slide.objects.get(pk="spawn").all_phases is True
    assert Slide.objects.get(pk="welcome").phases.count() == 2


def test_second_run_creates_nothing(content):
    report = load_all(settings.SIGNAGE_CONTENT_DIR)
    assert report.created == 0
    assert Slide.objects.count() == 25
    assert ScheduleEntry.objects.count() == 17


def test_admin_edits_survive_unless_overwritten(content):
    slide = Slide.objects.get(pk="welcome")
    slide.title_hu = "Szerkesztve"
    slide.origin = Slide.Origin.ADMIN
    slide.save()
    report = load_all(settings.SIGNAGE_CONTENT_DIR, only={"slides"})
    assert "slide welcome" in report.skipped
    assert Slide.objects.get(pk="welcome").title_hu == "Szerkesztve"
    load_all(settings.SIGNAGE_CONTENT_DIR, only={"slides"}, overwrite=True)
    assert Slide.objects.get(pk="welcome").title_hu == "Üdv a bulin, nerdek!"
