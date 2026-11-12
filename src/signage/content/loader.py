"""Import content/*.yaml into the database. Idempotent: existing rows are matched by
their key (slide id, schedule key, game slug, phase key, template key) and only updated
while they still carry the seed origin, or when `overwrite` is requested.

The import runs on every start of the stack, so it has to leave an organizer's decisions
alone. A row edited in the admin keeps its values. A row deleted in the admin stays
deleted. With `prune`, a row that came from the YAML and is no longer in it is removed;
rows created or edited in the admin never are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

from django.db import transaction
from django.utils.dateparse import parse_datetime

from signage.content import lint
from signage.content.safe_yaml import load_yaml
from signage.models import (
    LANGS,
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

FILES = {
    "event": "event.yaml",
    "games": "games.yaml",
    "schedule": "schedule.yaml",
    "slides": "slides.yaml",
    "announcements": "announcements.yaml",
}


@dataclass
class Report:
    created: int = 0
    updated: int = 0
    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: Report) -> None:
        self.created += other.created
        self.updated += other.updated
        self.removed.extend(other.removed)
        self.skipped.extend(other.skipped)
        self.warnings.extend(other.warnings)

    def summary(self) -> str:
        text = f"{self.created} created, {self.updated} updated"
        if self.removed:
            text += f", {len(self.removed)} removed (no longer in the YAML)"
        if self.skipped:
            text += f", {len(self.skipped)} skipped (edited or deleted in the admin)"
        return text


def read_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lint.lint_text(text, str(path))
    data = load_yaml(text) or {}
    if not isinstance(data, dict):
        raise lint.LintError(f"{path}: top level must be a mapping")
    return data


def read_content_dir(directory: Path) -> dict[str, dict]:
    data = {key: read_yaml(directory / name) for key, name in FILES.items()}
    lint.lint_all(
        data["event"], data["slides"], data["schedule"], data["games"], data["announcements"]
    )
    return data


def _parse_time(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def _aware(value: str) -> datetime:
    parsed = parse_datetime(value)
    if parsed is None or parsed.tzinfo is None:
        raise lint.LintError(f"event.yaml: {value!r} is not an ISO datetime with an offset")
    return parsed


def _coordinate(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value)).quantize(Decimal("0.0000001"))


def _bilingual(data: dict, key: str) -> dict[str, str]:
    value = data.get(key) or {}
    return {lang: value.get(lang, "") for lang in LANGS}


def _was_removed(model, key: str, report: Report, label: str, *, overwrite: bool) -> bool:
    """Whether an organizer deleted this row, which a plain import respects. An import
    that overwrites brings the row back and forgets the deletion."""
    if key not in RemovedSeed.keys_for(model):
        return False
    if overwrite:
        RemovedSeed.forget(model, key)
        return False
    report.skipped.append(f"{label} (deleted in the admin)")
    return True


def _seed_row(model, report: Report, label: str, lookup: dict, values: dict, *, overwrite: bool):
    """Create or update one seeded row. A row saved in the admin keeps its values unless
    `overwrite` is requested; a row the seed touches goes back to the seed origin."""
    existing = model.objects.filter(**lookup).first()
    if existing and existing.origin == Origin.ADMIN and not overwrite:
        report.skipped.append(label)
        return existing
    if existing is None and _was_removed(
        model, str(next(iter(lookup.values()))), report, label, overwrite=overwrite
    ):
        return None
    row = existing or model(**lookup)
    for attr, value in values.items():
        setattr(row, attr, value)
    row.origin = Origin.SEED
    # The database would refuse a text that is too long with an error of its own, or keep
    # it, depending on which database it is. This says which field of which row it is.
    row.full_clean()
    row.save()
    if existing:
        report.updated += 1
    else:
        report.created += 1
    return row


def _prune(model, report: Report, label: str, keys: set[str], *, prune: bool) -> None:
    """Remove the rows that came from the YAML and have left it. The YAML is what such a
    row is; one that an organizer created or edited is theirs and stays."""
    if not prune:
        return
    field_name = model.seed_key_field
    gone = model.objects.filter(origin=Origin.SEED).exclude(**{f"{field_name}__in": keys})
    for row in gone:
        report.removed.append(f"{label} {row.seed_key}")
    gone.delete()


@transaction.atomic
def load_event(data: dict, *, overwrite: bool = False, prune: bool = False) -> Report:
    report = Report()
    event = Event.get_solo()
    is_new = event.venue_name == "" and not event.wifi_ssid
    if is_new or overwrite:
        ev, venue, wifi = data["event"], data["venue"], data["wifi"]
        event.name = ev["name"]
        event.tagline = ev.get("tagline", "")
        event.starts_at = _aware(ev["starts_at"])
        event.ends_at = _aware(ev["ends_at"])
        event.timezone = ev.get("timezone", "Europe/Budapest")
        event.venue_name = venue["name"]
        event.venue_address = venue["address"]
        event.venue_lat = _coordinate(venue.get("lat"))
        event.venue_lng = _coordinate(venue.get("lng"))
        for key in ("entrance_note", "parking", "assembly_point"):
            for lang, text in _bilingual(venue, key).items():
                setattr(event, f"{key}_{lang}", text)
        event.wifi_ssid = wifi.get("ssid", "")
        event.wifi_password = wifi.get("password", "")
        event.wifi_security = wifi.get("security", "WPA")
        for lang, text in _bilingual(wifi, "note").items():
            setattr(event, f"wifi_note_{lang}", text)
        event.links = dict(data.get("links", {}))
        event.email = data.get("links", {}).get("email", "")
        event.organizers = list(data.get("organizers", []))
        event.full_clean()
        event.save()
        report.created += int(is_new)
        report.updated += int(not is_new)
    else:
        report.skipped.append("event (use --overwrite to replace the admin values)")

    for order, phase in enumerate(data["phases"]):
        _seed_row(
            Phase,
            report,
            f"phase {phase['key']}",
            {"key": phase["key"]},
            {
                "name_hu": phase["hu"],
                "name_en": phase["en"],
                "starts": _parse_time(phase["starts"]),
                "day_offset": int(phase.get("day_offset", 0)),
                "order": order,
            },
            overwrite=overwrite,
        )
    _prune(Phase, report, "phase", {phase["key"] for phase in data["phases"]}, prune=prune)
    event.refresh_from_db()
    if event.current_phase is None:
        event.current_phase = Phase.objects.order_by("order").first()
        event.save(update_fields=["current_phase"])
    return report


@transaction.atomic
def load_games(data: dict, *, overwrite: bool = False, prune: bool = False) -> Report:
    report = Report()
    for game in data["games"]:
        color = game.get("color") or {}
        _seed_row(
            Game,
            report,
            f"game {game['slug']}",
            {"slug": game["slug"]},
            {
                "name": game["name"],
                "short": game.get("short") or game["name"],
                "hosted": bool(game.get("hosted", False)),
                "tournament": bool(game.get("tournament", False)),
                "projectile_keys": list(game.get("projectile_keys", [])),
                "color_bg": color.get("bg", "#777777"),
                "color_text": color.get("text", "#000000"),
            },
            overwrite=overwrite,
        )
    _prune(Game, report, "game", {game["slug"] for game in data["games"]}, prune=prune)
    return report


@transaction.atomic
def load_schedule(data: dict, *, overwrite: bool = False, prune: bool = False) -> Report:
    report = Report()
    games = {g.slug: g for g in Game.objects.all()}
    for order, entry in enumerate(data["entries"]):
        title = _bilingual(entry, "title")
        note = _bilingual(entry, "note")
        _seed_row(
            ScheduleEntry,
            report,
            f"schedule {entry['key']}",
            {"key": entry["key"]},
            {
                "time": _parse_time(entry["time"]),
                "day_offset": int(entry.get("day_offset", 0)),
                "type": entry["type"],
                "game": games.get(entry.get("game") or ""),
                "label": entry.get("label") or "",
                "title_hu": title["hu"],
                "title_en": title["en"],
                "note_hu": note["hu"],
                "note_en": note["en"],
                "order": order,
            },
            overwrite=overwrite,
        )
    keys = {entry["key"] for entry in data["entries"]}
    _prune(ScheduleEntry, report, "schedule", keys, prune=prune)
    return report


def _slide_defaults(data: dict, defaults: dict, order: int) -> dict:
    values: dict = {
        "layout": data["layout"],
        "source": data.get("source", "static"),
        "all_phases": data.get("phases") == "all",
        "duration_seconds": int(data.get("duration_seconds", defaults.get("duration_seconds", 15))),
        "bilingual_mode": data.get("bilingual_mode", defaults.get("bilingual_mode", "alternate")),
        "priority": int(data.get("priority", defaults.get("priority", 50))),
        "order": order,
        "notes": (data.get("notes") or "").strip(),
        "labels": {},
    }
    for key in ("kicker", "title", "body", "footer", "empty"):
        for lang, text in _bilingual(data, key).items():
            values[f"{key}_{lang}"] = text
    for index, column in enumerate(data.get("columns", [])[:2], start=1):
        for lang, text in _bilingual(column, "title").items():
            values[f"column{index}_title_{lang}"] = text
    for group in ("columns_labels", "sections"):
        for key, value in (data.get(group) or {}).items():
            values["labels"][key] = {lang: value[lang] for lang in LANGS}
    link = data.get("link") or {}
    values["link_url"] = link.get("url", "")
    values["link_qr"] = bool(link.get("qr", False))
    for lang, text in _bilingual(link, "label").items():
        values[f"link_label_{lang}"] = text
    return values


def _replace_items(slide: Slide, data: dict) -> None:
    slide.items.all().delete()
    rows: list[SlideItem] = []
    for order, item in enumerate(data.get("items", [])):
        rows.append(
            SlideItem(
                slide=slide,
                column=1,
                order=order,
                text_hu=item["hu"],
                text_en=item["en"],
                icon=item.get("icon", ""),
            )
        )
    for column, column_data in enumerate(data.get("columns", [])[:2], start=1):
        for order, item in enumerate(column_data.get("items", [])):
            rows.append(
                SlideItem(
                    slide=slide,
                    column=column,
                    order=order,
                    text_hu=item["hu"],
                    text_en=item["en"],
                    icon=item.get("icon", ""),
                )
            )
    for row in rows:
        row.full_clean(exclude=["slide"])
    SlideItem.objects.bulk_create(rows)


@transaction.atomic
def load_slides(data: dict, *, overwrite: bool = False, prune: bool = False) -> Report:
    report = Report()
    defaults = data.get("defaults", {})
    phases = {p.key: p for p in Phase.objects.all()}
    for order, slide_data in enumerate(data["slides"]):
        key = slide_data["id"]
        existing = Slide.objects.filter(pk=key).first()
        if existing and existing.origin == Origin.ADMIN and not overwrite:
            report.skipped.append(f"slide {key}")
            continue
        if existing is None and _was_removed(
            Slide, key, report, f"slide {key}", overwrite=overwrite
        ):
            continue
        values = _slide_defaults(slide_data, defaults, order)
        values["origin"] = Origin.SEED
        if existing:
            for attr, value in values.items():
                setattr(existing, attr, value)
            slide = existing
            report.updated += 1
        else:
            slide = Slide(key=key, **values)
            report.created += 1
        slide.full_clean(exclude=["phases"])
        slide.save()
        wanted = slide_data.get("phases")
        if wanted != "all" and (missing := set(wanted) - phases.keys()):
            report.warnings.append(
                f"slide {key}: phases deleted in the admin are omitted: "
                f"{', '.join(sorted(missing))}"
            )
        slide.phases.set([] if wanted == "all" else [phases[k] for k in wanted if k in phases])
        _replace_items(slide, slide_data)
    _prune(Slide, report, "slide", {slide["id"] for slide in data["slides"]}, prune=prune)
    return report


@transaction.atomic
def load_announcements(data: dict, *, overwrite: bool = False, prune: bool = False) -> Report:
    report = Report()
    for template in data["templates"]:
        text = _bilingual(template, "text")
        _seed_row(
            AnnouncementTemplate,
            report,
            f"template {template['key']}",
            {"key": template["key"]},
            {
                "level": template["level"],
                "takeover": bool(template.get("takeover", False)),
                "text_hu": text["hu"],
                "text_en": text["en"],
            },
            overwrite=overwrite,
        )
    keys = {template["key"] for template in data["templates"]}
    _prune(AnnouncementTemplate, report, "template", keys, prune=prune)
    return report


LOADERS = {
    "event": load_event,
    "games": load_games,
    "schedule": load_schedule,
    "slides": load_slides,
    "announcements": load_announcements,
}


@transaction.atomic
def load_all(
    directory: Path,
    *,
    only: set[str] | None = None,
    overwrite: bool = False,
    prune: bool = True,
) -> Report:
    """Load the content directory, which is the whole of the seeded content: what has left
    its files is removed from the database unless `prune` is turned off."""
    data = read_content_dir(directory)
    wanted = only or set(FILES)
    report = Report()
    # In this order: the schedule refers to games, and slides to phases.
    for name, loader in LOADERS.items():
        if name in wanted:
            report.merge(loader(data[name], overwrite=overwrite, prune=prune))
    return report
