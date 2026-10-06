"""Import content/*.yaml into the database. Idempotent: existing rows are matched by
their natural key and only updated when they still carry the seed origin or when
`overwrite` is requested."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

import yaml
from django.db import transaction
from django.utils.dateparse import parse_datetime

from signage.content import lint
from signage.models import (
    LANGS,
    AnnouncementTemplate,
    Event,
    Game,
    Phase,
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
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: Report) -> None:
        self.created += other.created
        self.updated += other.updated
        self.skipped.extend(other.skipped)
        self.warnings.extend(other.warnings)

    def summary(self) -> str:
        text = f"{self.created} created, {self.updated} updated"
        if self.skipped:
            text += f", {len(self.skipped)} skipped (edited in the admin)"
        return text


def read_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lint.lint_text(text, str(path))
    data = yaml.safe_load(text) or {}
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


@transaction.atomic
def load_event(data: dict, *, overwrite: bool = False) -> Report:
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
        _, created = Phase.objects.update_or_create(
            key=phase["key"],
            defaults={
                "name_hu": phase["hu"],
                "name_en": phase["en"],
                "starts": _parse_time(phase["starts"]),
                "day_offset": int(phase.get("day_offset", 0)),
                "order": order,
            },
        )
        report.created += int(created)
        report.updated += int(not created)
    if event.current_phase is None:
        event.current_phase = Phase.objects.order_by("order").first()
        event.save(update_fields=["current_phase"])
    return report


@transaction.atomic
def load_games(data: dict) -> Report:
    report = Report()
    for game in data["games"]:
        color = game.get("color") or {}
        _, created = Game.objects.update_or_create(
            slug=game["slug"],
            defaults={
                "name": game["name"],
                "short": game.get("short") or game["name"],
                "hosted": bool(game.get("hosted", False)),
                "tournament": bool(game.get("tournament", False)),
                "projectile_keys": list(game.get("projectile_keys", [])),
                "color_bg": color.get("bg", "#777777"),
                "color_text": color.get("text", "#000000"),
            },
        )
        report.created += int(created)
        report.updated += int(not created)
    return report


@transaction.atomic
def load_schedule(data: dict) -> Report:
    report = Report()
    games = {g.slug: g for g in Game.objects.all()}
    for order, entry in enumerate(data["entries"]):
        title = _bilingual(entry, "title")
        note = _bilingual(entry, "note")
        _, created = ScheduleEntry.objects.update_or_create(
            time=_parse_time(entry["time"]),
            day_offset=int(entry.get("day_offset", 0)),
            title_hu=title["hu"],
            defaults={
                "type": entry["type"],
                "game": games.get(entry.get("game") or ""),
                "label": entry.get("label") or "",
                "title_en": title["en"],
                "note_hu": note["hu"],
                "note_en": note["en"],
                "order": order,
            },
        )
        report.created += int(created)
        report.updated += int(not created)
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
    SlideItem.objects.bulk_create(rows)


@transaction.atomic
def load_slides(data: dict, *, overwrite: bool = False) -> Report:
    report = Report()
    defaults = data.get("defaults", {})
    phases = {p.key: p for p in Phase.objects.all()}
    for order, slide_data in enumerate(data["slides"]):
        key = slide_data["id"]
        existing = Slide.objects.filter(pk=key).first()
        if existing and existing.origin == Slide.Origin.ADMIN and not overwrite:
            report.skipped.append(f"slide {key}")
            continue
        values = _slide_defaults(slide_data, defaults, order)
        values["origin"] = Slide.Origin.SEED
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
        slide.phases.set([] if wanted == "all" else [phases[k] for k in wanted])
        _replace_items(slide, slide_data)
    return report


@transaction.atomic
def load_announcements(data: dict) -> Report:
    report = Report()
    for template in data["templates"]:
        text = _bilingual(template, "text")
        _, created = AnnouncementTemplate.objects.update_or_create(
            key=template["key"],
            defaults={
                "level": template["level"],
                "takeover": bool(template.get("takeover", False)),
                "text_hu": text["hu"],
                "text_en": text["en"],
            },
        )
        report.created += int(created)
        report.updated += int(not created)
    return report


def load_all(directory: Path, *, only: set[str] | None = None, overwrite: bool = False) -> Report:
    data = read_content_dir(directory)
    wanted = only or set(FILES)
    report = Report()
    if "event" in wanted:
        report.merge(load_event(data["event"], overwrite=overwrite))
    if "games" in wanted:
        report.merge(load_games(data["games"]))
    if "schedule" in wanted:
        report.merge(load_schedule(data["schedule"]))
    if "slides" in wanted:
        report.merge(load_slides(data["slides"], overwrite=overwrite))
    if "announcements" in wanted:
        report.merge(load_announcements(data["announcements"]))
    return report
