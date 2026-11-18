"""Organizers and the content import changing the same rows at the same time, in overlapping
transactions as PostgreSQL runs them in production. SQLite runs one writer at a time, so
these are skipped there."""

import threading

import pytest
from django.conf import settings
from django.db import connection, transaction
from django.test import Client
from django.urls import reverse

from signage.concurrency import locked
from signage.content import loader
from signage.models import Origin, Slide
from signage.tests.test_concurrent_edits import opened_version, slide_form

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(connection.vendor != "postgresql", reason="needs PostgreSQL"),
    pytest.mark.django_db(transaction=True),
]
WAIT = 10
ORGANIZER_TITLE = "Szervezői cím"


def in_thread(work) -> tuple[threading.Thread, list[BaseException]]:
    """Runs `work` in a thread with a database connection of its own."""
    errors: list[BaseException] = []

    def run():
        try:
            work()
        except BaseException as error:
            errors.append(error)
        finally:
            connection.close()

    thread = threading.Thread(target=run)
    thread.start()
    return thread, errors


def house_rules_yaml() -> dict:
    slides = loader.read_content_dir(settings.SIGNAGE_CONTENT_DIR)["slides"]
    return {**slides, "slides": [s for s in slides["slides"] if s["id"] == "house_rules"]}


def organizer_saves(holding: threading.Event | None = None, release=None) -> None:
    """What saving the slide's change page writes, in a transaction of its own."""
    with transaction.atomic():
        slide = locked(Slide.objects.filter(pk="house_rules"))
        slide.title_hu = ORGANIZER_TITLE
        slide.origin = Origin.ADMIN
        slide.save()
        if holding is not None:
            holding.set()
            assert release.wait(WAIT)


def test_an_organizer_saving_while_the_import_decides_keeps_the_organizers_change(
    content, monkeypatch
):
    decided, resume = threading.Event(), threading.Event()
    real = loader.locked

    def pausing(queryset):
        row = real(queryset)
        if queryset.model is Slide:
            decided.set()
            assert resume.wait(WAIT)
        return row

    monkeypatch.setattr(loader, "locked", pausing)
    importing, import_errors = in_thread(lambda: loader.load_slides(house_rules_yaml()))
    assert decided.wait(WAIT)

    saved = threading.Event()
    saving, save_errors = in_thread(lambda: organizer_saves() or saved.set())
    # The import holds the row it read, so the organizer's save waits for it to finish.
    assert not saved.wait(1)
    resume.set()
    importing.join(WAIT)
    saving.join(WAIT)
    assert not import_errors and not save_errors
    slide = Slide.objects.get(pk="house_rules")
    assert (slide.title_hu, slide.origin) == (ORGANIZER_TITLE, Origin.ADMIN)


def test_the_import_leaves_alone_a_change_an_organizer_is_saving(content):
    holding, release = threading.Event(), threading.Event()
    saving, save_errors = in_thread(lambda: organizer_saves(holding, release))
    assert holding.wait(WAIT)

    reports = []
    imported = threading.Event()
    importing, import_errors = in_thread(
        lambda: reports.append(loader.load_slides(house_rules_yaml())) or imported.set()
    )
    # The import reads the row with a lock, so it waits for the organizer's save.
    assert not imported.wait(1)
    release.set()
    saving.join(WAIT)
    importing.join(WAIT)
    assert not save_errors and not import_errors
    slide = Slide.objects.get(pk="house_rules")
    assert (slide.title_hu, slide.origin) == (ORGANIZER_TITLE, Origin.ADMIN)
    assert "slide house_rules" in reports[0].skipped


def test_of_two_organizers_saving_pages_opened_together_one_is_asked_to_look_again(
    content, admin_user
):
    url = reverse("admin:signage_slide_change", args=["house_rules"])
    clients = [Client(), Client()]
    for client in clients:
        client.force_login(admin_user)
    version = opened_version(clients[0].get(url))
    slide = Slide.objects.get(pk="house_rules")
    together = threading.Barrier(2)
    answers = []

    def save(client, title):
        together.wait(WAIT)
        answers.append(client.post(url, slide_form(slide, version, title_hu=title)).status_code)

    threads = [
        in_thread(lambda client=client, title=title: save(client, title))
        for client, title in zip(clients, ["Első szervező", "Második szervező"], strict=True)
    ]
    for thread, errors in threads:
        thread.join(WAIT)
        assert not errors
    assert sorted(answers) == [200, 302]
    assert Slide.objects.get(pk="house_rules").title_hu in ("Első szervező", "Második szervező")
