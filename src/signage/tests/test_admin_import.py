import yaml
from django.core.files.uploadedfile import SimpleUploadedFile

from signage.models import Event, Origin, ScheduleEntry, Slide


def _upload(name: str, document: dict) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, yaml.safe_dump(document, allow_unicode=True).encode("utf-8"))


def test_import_rejects_a_slide_without_english(admin_client, content):
    document = {
        "slides": [{"id": "lonely", "layout": "list", "phases": "all", "title": {"hu": "Csak"}}]
    }
    response = admin_client.post(
        "/admin/signage/slide/import-yaml/", {"file": _upload("slides.yaml", document)}
    )
    assert response.status_code == 200
    assert "Import failed" in response.content.decode()
    assert not Slide.objects.filter(pk="lonely").exists()


def test_import_rejects_undecodable_and_unparseable_files(admin_client, content):
    for payload in (b"\xff\xfe\x00bad", b"entries: [unclosed", b"- just\n- a list\n"):
        response = admin_client.post(
            "/admin/signage/scheduleentry/import-yaml/",
            {"file": SimpleUploadedFile("schedule.yaml", payload)},
        )
        assert response.status_code == 200
        assert "Import failed" in response.content.decode()


def test_import_skips_admin_rows_unless_overwrite_is_ticked(admin_client, content):
    entry = ScheduleEntry.objects.get(key="tf2")
    entry.title_en = "Hats"
    entry.origin = Origin.ADMIN
    entry.save()
    document = {
        "entries": [
            {
                "key": "tf2",
                "time": "17:00",
                "type": "play",
                "game": "tf2",
                "label": "TF2",
                "title": {"hu": "Csapat", "en": "Team"},
            }
        ]
    }
    response = admin_client.post(
        "/admin/signage/scheduleentry/import-yaml/", {"file": _upload("schedule.yaml", document)}
    )
    assert response.status_code == 302
    assert ScheduleEntry.objects.get(key="tf2").title_en == "Hats"

    response = admin_client.post(
        "/admin/signage/scheduleentry/import-yaml/",
        {"file": _upload("schedule.yaml", document), "overwrite": "on"},
    )
    assert response.status_code == 302
    assert ScheduleEntry.objects.get(key="tf2").title_en == "Team"
    assert ScheduleEntry.objects.get(key="tf2").origin == Origin.SEED


def test_phase_buttons_post_to_the_phase_view(admin_client, content):
    page = admin_client.get("/admin/signage/event/").content.decode()
    # The buttons redirect the admin's own form; no second form is nested inside it.
    assert ' action="/admin/signage/event/set-phase/' not in page
    assert 'formaction="/admin/signage/event/set-phase/play/"' in page
    response = admin_client.post("/admin/signage/event/set-phase/play/")
    assert response.status_code == 302
    event = Event.get_solo()
    assert event.current_phase.key == "play" and event.phase_mode == Event.PhaseMode.MANUAL
