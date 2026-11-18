"""An organizer's change page refuses to save over a change made since it was opened, by
another organizer or by the content import."""

import re

from django.urls import reverse

from signage.admin import CHANGED_MEANWHILE
from signage.models import Event, Origin, Slide


def opened_version(page) -> str:
    return re.search(r'name="row_version" value="([0-9a-f]+)"', page.content.decode())[1]


def slide_form(slide: Slide, version: str, **changes) -> dict:
    return {
        "row_version": version,
        "layout": slide.layout,
        "source": slide.source,
        "enabled": "on",
        "all_phases": "on",
        "duration_seconds": str(slide.duration_seconds),
        "bilingual_mode": slide.bilingual_mode,
        "priority": str(slide.priority),
        "order": str(slide.order),
        "title_hu": slide.title_hu,
        "title_en": slide.title_en,
        "labels": "{}",
        "items-TOTAL_FORMS": "0",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "1000",
        **changes,
    }


def test_a_change_made_since_the_page_was_opened_is_not_saved_over(admin_client, content):
    url = reverse("admin:signage_slide_change", args=["house_rules"])
    version = opened_version(admin_client.get(url))
    # Another organizer saves the same slide meanwhile.
    Slide.objects.filter(pk="house_rules").update(title_hu="A másik szervező címe")

    slide = Slide.objects.get(pk="house_rules")
    response = admin_client.post(url, slide_form(slide, version, title_hu="Az én címem"))
    assert response.status_code == 200
    assert str(CHANGED_MEANWHILE) in response.content.decode()
    assert Slide.objects.get(pk="house_rules").title_hu == "A másik szervező címe"


def test_a_page_opened_after_the_last_change_saves(admin_client, content):
    url = reverse("admin:signage_slide_change", args=["house_rules"])
    version = opened_version(admin_client.get(url))
    slide = Slide.objects.get(pk="house_rules")
    response = admin_client.post(url, slide_form(slide, version, title_hu="Az én címem"))
    assert response.status_code == 302
    saved = Slide.objects.get(pk="house_rules")
    assert (saved.title_hu, saved.origin) == ("Az én címem", Origin.ADMIN)


def test_the_event_page_also_refuses_to_undo_a_change_made_meanwhile(admin_client, event):
    url = reverse("admin:signage_event_change")
    page = admin_client.get(url)
    version = opened_version(page)
    Event.objects.filter(pk=event.pk).update(tagline="Changed meanwhile")
    form = {name: value for name, value in page.context["adminform"].form.initial.items()}
    form = {key: "" if value is None else value for key, value in form.items()}
    form.update(row_version=version, name="Ctrl-Alt-GG", tagline="Mine")
    response = admin_client.post(url, form)
    assert response.status_code == 200
    assert str(CHANGED_MEANWHILE) in response.content.decode()
    assert Event.objects.get(pk=event.pk).tagline == "Changed meanwhile"
