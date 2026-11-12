import pytest
import yaml
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile

from signage.models import Event, Origin, RemovedSeed, ScheduleEntry, Slide


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


def test_an_unquoted_time_is_an_import_error_not_a_crash(admin_client, content):
    """YAML reads 17:00 without quotes as a number, which used to answer 500."""
    payload = (
        b"entries:\n"
        b"  - key: tf2\n"
        b"    time: 17:00\n"
        b"    type: play\n"
        b"    title: {hu: Csapat, en: Team}\n"
    )
    response = admin_client.post(
        "/admin/signage/scheduleentry/import-yaml/",
        {"file": SimpleUploadedFile("schedule.yaml", payload)},
    )
    assert response.status_code == 200
    assert "quoted time" in response.content.decode()


def test_files_of_another_shape_are_import_errors(admin_client, content):
    for document in (
        {"entries": "tf2"},
        {"entries": [{"key": "tf2", "time": "17:00", "type": "play", "title": "Csapat"}]},
        {
            "slides": [
                {
                    "id": "x",
                    "layout": "list",
                    "phases": "all",
                    "title": {"hu": "a", "en": "b"},
                    "items": "one, two",
                }
            ]
        },
    ):
        name = "slide" if "slides" in document else "scheduleentry"
        response = admin_client.post(
            f"/admin/signage/{name}/import-yaml/", {"file": _upload("content.yaml", document)}
        )
        assert response.status_code == 200, document
        assert "Import failed" in response.content.decode()


def test_import_refuses_a_file_too_large_to_be_content(admin_client, content, settings):
    settings.SIGNAGE_IMPORT_MAX_BYTES = 64
    response = admin_client.post(
        "/admin/signage/slide/import-yaml/",
        {"file": SimpleUploadedFile("slides.yaml", b"slides: []\n" + b"#" * 100)},
    )
    assert response.status_code == 200
    assert "too large" in response.content.decode()


def test_import_refuses_a_tiny_alias_document_before_it_can_expand(admin_client, content):
    payload = b"slides: &slides [{id: x}]\nrepeat: *slides\n"
    response = admin_client.post(
        "/admin/signage/slide/import-yaml/",
        {"file": SimpleUploadedFile("slides.yaml", payload)},
    )
    assert response.status_code == 200
    assert "aliases are not supported" in response.content.decode()
    assert Slide.objects.count() == 27


def test_import_removes_missing_seed_rows_only_when_asked(admin_client, content):
    document = {
        "entries": [
            {
                "key": "tf2",
                "time": "17:00",
                "type": "play",
                "title": {"hu": "Csapat", "en": "Team"},
            }
        ]
    }
    admin_client.post(
        "/admin/signage/scheduleentry/import-yaml/", {"file": _upload("schedule.yaml", document)}
    )
    assert ScheduleEntry.objects.count() == 17
    admin_client.post(
        "/admin/signage/scheduleentry/import-yaml/",
        {"file": _upload("schedule.yaml", document), "prune": "on"},
    )
    assert list(ScheduleEntry.objects.values_list("key", flat=True)) == ["tf2"]


@pytest.fixture
def staff_client(client, db):
    """Someone with an admin login and no permissions at all."""
    user = User.objects.create_user("helper", password="x", is_staff=True)
    client.force_login(user)
    client.user = user
    return client


def test_custom_views_need_the_permission_they_use(staff_client, content):
    """A staff account alone must not be able to replace the slides, change the phase or
    put a takeover on every screen."""
    document = {"slides": []}
    assert (
        staff_client.post(
            "/admin/signage/slide/import-yaml/", {"file": _upload("slides.yaml", document)}
        ).status_code
        == 403
    )
    assert staff_client.get("/admin/signage/event/import-yaml/").status_code == 403
    assert staff_client.post("/admin/signage/event/set-phase/play/").status_code == 403
    assert Event.get_solo().current_phase.key != "play"
    assert staff_client.get("/admin/signage/announcement/from-template/").status_code == 403
    assert staff_client.post("/admin/signage/announcement/from-template/").status_code == 403


def test_the_right_permission_opens_each_view(staff_client, content):
    def grant(*codenames):
        staff_client.user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))

    grant("change_event")
    assert staff_client.post("/admin/signage/event/set-phase/play/").status_code == 302
    assert Event.get_solo().current_phase.key == "play"
    # The event file also holds the phases, so importing it takes the rights to those too.
    assert staff_client.get("/admin/signage/event/import-yaml/").status_code == 403
    grant("add_phase", "change_phase", "delete_phase")
    assert staff_client.get("/admin/signage/event/import-yaml/").status_code == 200

    grant("view_slide", "change_slide")
    assert staff_client.get("/admin/signage/slide/import-yaml/").status_code == 403
    assert "import-yaml" not in staff_client.get("/admin/signage/slide/").content.decode()
    grant("add_slide")
    assert staff_client.get("/admin/signage/slide/import-yaml/").status_code == 200
    assert "import-yaml" in staff_client.get("/admin/signage/slide/").content.decode()

    grant("add_announcement")
    assert staff_client.get("/admin/signage/announcement/from-template/").status_code == 200


def test_pruning_an_import_requires_delete_permission(staff_client, content):
    staff_client.user.user_permissions.add(
        *Permission.objects.filter(codename__in=("add_slide", "change_slide"))
    )
    document = {"slides": []}
    response = staff_client.post(
        "/admin/signage/slide/import-yaml/",
        {"file": _upload("slides.yaml", document), "prune": "on"},
    )
    assert response.status_code == 403
    assert Slide.objects.count() == 27


def test_a_seeded_row_deleted_in_the_admin_does_not_come_back(admin_client, content, settings):
    from signage.content.loader import load_all

    response = admin_client.post("/admin/signage/slide/food/delete/", {"post": "yes"})
    assert response.status_code == 302
    admin_client.post(
        "/admin/signage/scheduleentry/",
        {
            "action": "delete_selected",
            "_selected_action": [ScheduleEntry.objects.get(key="tf2").pk],
            "post": "yes",
        },
    )
    assert set(RemovedSeed.objects.values_list("model", "key")) == {
        ("slide", "food"),
        ("scheduleentry", "tf2"),
    }
    load_all(settings.SIGNAGE_CONTENT_DIR)
    assert not Slide.objects.filter(pk="food").exists()
    assert not ScheduleEntry.objects.filter(key="tf2").exists()

    # Removing the entry is how an organizer changes their mind.
    removed = RemovedSeed.objects.get(model="slide")
    admin_client.post(f"/admin/signage/removedseed/{removed.pk}/delete/", {"post": "yes"})
    load_all(settings.SIGNAGE_CONTENT_DIR)
    assert Slide.objects.filter(pk="food").exists()


def test_bulk_actions_make_a_slide_the_organizers_like_the_checkbox_does(admin_client, content):
    assert Slide.objects.get(pk="food").origin == Origin.SEED
    admin_client.post(
        "/admin/signage/slide/", {"action": "disable_slides", "_selected_action": ["food"]}
    )
    slide = Slide.objects.get(pk="food")
    assert slide.enabled is False and slide.origin == Origin.ADMIN
