"""Validation rules for content/*.yaml. Pure functions, no Django imports, so
scripts/render_content.py can use them without the application installed."""

from __future__ import annotations

import re
from collections.abc import Iterable

BANNED_GLYPHS = {
    chr(0x2013): "en dash",
    chr(0x2014): "em dash",
    chr(0x2026): "ellipsis character",
    chr(0x2018): "curly quote",
    chr(0x2019): "curly quote",
    chr(0x201C): "curly quote",
    chr(0x201D): "curly quote",
    chr(0x00A0): "non-breaking space",
}

LAYOUTS = {
    "hero",
    "list",
    "split",
    "qr",
    "credentials",
    "now_next",
    "schedule",
    "servers",
    "tournament",
    "streams",
    "countdown",
}
SOURCES = {
    "static",
    "live:schedule",
    "live:clock",
    "live:projectile",
    "live:bracket",
    "live:streams",
}
LANGS = ("hu", "en")
MAX_ITEMS = 6
MAX_SPLIT_ITEMS = 4

# A placeholder is a lowercase name in braces, such as {wifi_ssid} or {team1}. Any other
# brace is ordinary text.
PLACEHOLDER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")
# The names the event has a value for, which is what a slide may use.
EVENT_PLACEHOLDERS = (
    "wifi_ssid",
    "wifi_password",
    "wifi_note",
    "venue_name",
    "venue_address",
    "starts_at_time",
    "starts_at_date",
    "assembly_point",
    "email",
)
TIME_RE = re.compile(r"([01]?\d|2[0-3]):[0-5]\d")


class LintError(Exception):
    pass


def unknown_placeholders(text: object) -> list[str]:
    """The {names} in a text that the event has no value for."""
    if not isinstance(text, str):
        return []
    return sorted(set(PLACEHOLDER_RE.findall(text)) - set(EVENT_PLACEHOLDERS))


def require_list(value: object, where: str) -> list:
    if not isinstance(value, list):
        raise LintError(f"{where}: expected a list")
    return value


def require_mappings(value: object, where: str) -> list[dict]:
    rows = require_list(value, where)
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise LintError(f"{where}[{index}]: expected a mapping")
    return rows


def require_time(value: object, where: str) -> str:
    """A wall-clock time. YAML reads an unquoted 10:00 as the number 600, so the quotes are
    part of the format."""
    if not isinstance(value, str) or not TIME_RE.fullmatch(value):
        raise LintError(f'{where}: expected a quoted time such as "10:00", found {value!r}')
    return value


def require_day_offset(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 7:
        raise LintError(f"{where}: day_offset must be a whole number of days, found {value!r}")
    return value


def require_placeholders(value: dict, where: str) -> None:
    for lang in LANGS:
        if unknown := unknown_placeholders(value.get(lang)):
            names = ", ".join(f"{{{name}}}" for name in unknown)
            raise LintError(
                f"{where}.{lang}: unknown placeholder {names}; "
                f"the event provides {', '.join(EVENT_PLACEHOLDERS)}"
            )


def lint_text(text: str, where: str) -> None:
    for lineno, line in enumerate(text.splitlines(), start=1):
        for glyph, label in BANNED_GLYPHS.items():
            if glyph in line:
                raise LintError(f"{where}:{lineno}: {label} found")


def require_bilingual(value: object, where: str) -> dict:
    if not isinstance(value, dict):
        raise LintError(f"{where}: expected a mapping with hu and en")
    for lang in LANGS:
        if not isinstance(value.get(lang), str) or not value[lang].strip():
            raise LintError(f"{where}: missing or empty '{lang}'")
    return value


def lint_slides(slides: dict, phases: Iterable[str]) -> None:
    phase_keys = set(phases)
    seen: set[str] = set()
    for slide in require_mappings(slides.get("slides", []), "slides.yaml:slides"):
        sid = slide.get("id")
        if not sid or sid in seen:
            raise LintError(f"slide id missing or duplicated: {sid!r}")
        seen.add(sid)
        where = f"slides.yaml:{sid}"
        if slide.get("layout") not in LAYOUTS:
            raise LintError(f"{where}: unknown layout {slide.get('layout')!r}")
        if slide.get("source", "static") not in SOURCES:
            raise LintError(f"{where}: unknown source {slide.get('source')!r}")
        slide_phases = slide.get("phases")
        if slide_phases != "all":
            if not isinstance(slide_phases, list) or not slide_phases:
                raise LintError(f"{where}: phases must be 'all' or a non-empty list")
            unknown = set(slide_phases) - phase_keys
            if unknown:
                raise LintError(f"{where}: unknown phases {sorted(unknown)}")
        if slide.get("bilingual_mode", "alternate") not in ("alternate", "stacked"):
            raise LintError(f"{where}: bilingual_mode must be alternate or stacked")
        if "title" not in slide:
            raise LintError(f"{where}: title is required")
        for key in ("kicker", "title", "body", "footer", "empty"):
            if key in slide:
                require_placeholders(require_bilingual(slide[key], f"{where}.{key}"), where)
        items = require_mappings(slide.get("items", []), f"{where}.items")
        if len(items) > MAX_ITEMS:
            raise LintError(f"{where}: at most {MAX_ITEMS} items are shown on one slide")
        for index, item in enumerate(items):
            require_placeholders(require_bilingual(item, f"{where}.items[{index}]"), where)
        columns = require_mappings(slide.get("columns", []), f"{where}.columns")
        if slide.get("layout") == "split" and len(columns) != 2:
            raise LintError(f"{where}: split layout needs exactly two columns")
        for cindex, column in enumerate(columns):
            here = f"{where}.columns[{cindex}]"
            require_placeholders(require_bilingual(column.get("title"), f"{here}.title"), where)
            column_items = require_mappings(column.get("items", []), f"{here}.items")
            if len(column_items) > MAX_SPLIT_ITEMS:
                raise LintError(f"{here}: at most {MAX_SPLIT_ITEMS} items are shown in one column")
            for index, item in enumerate(column_items):
                require_placeholders(require_bilingual(item, f"{here}.items[{index}]"), where)
        for group in ("columns_labels", "sections"):
            for key, value in (slide.get(group) or {}).items():
                require_bilingual(value, f"{where}.{group}.{key}")
        link = slide.get("link")
        if link is not None and not isinstance(link, dict):
            raise LintError(f"{where}.link: expected a mapping")
        if link and "label" in link:
            require_placeholders(require_bilingual(link["label"], f"{where}.link.label"), where)


def lint_schedule(schedule: dict, games: Iterable[str]) -> None:
    game_slugs = set(games)
    keys: set[str] = set()
    previous: tuple[int, str] | None = None
    entries = require_mappings(schedule.get("entries", []), "schedule.yaml:entries")
    for index, entry in enumerate(entries):
        where = f"schedule.yaml:entries[{index}]"
        key = entry.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,59}", key):
            raise LintError(f"{where}: key missing or not a lowercase slug: {key!r}")
        if key in keys:
            raise LintError(f"{where}: duplicated key {key!r}")
        keys.add(key)
        if entry.get("type") not in ("play", "break", "highlight"):
            raise LintError(f"{where}: type must be play, break or highlight")
        require_bilingual(entry.get("title"), f"{where}.title")
        if "note" in entry:
            require_bilingual(entry["note"], f"{where}.note")
        if entry.get("game") and entry["game"] not in game_slugs:
            raise LintError(f"{where}: unknown game slug {entry['game']!r}")
        hours, minutes = require_time(entry.get("time"), f"{where}.time").split(":")
        # Zero-padded, so that the comparison below reads 9:00 as earlier than 10:00.
        moment = (
            require_day_offset(entry.get("day_offset", 0), where),
            f"{int(hours):02d}:{minutes}",
        )
        # The entries are listed in the order they happen. One that goes back in time is
        # nearly always a slot after midnight that still says day 0: it would sort before
        # the event and never become the current one.
        if previous is not None and moment < previous:
            raise LintError(
                f"{where}: {entry['time']} on day {moment[0]} is before the entry above it; "
                "a slot after midnight needs day_offset: 1"
            )
        previous = moment


def lint_announcements(announcements: dict) -> None:
    templates = require_mappings(announcements.get("templates", []), "announcements.yaml:templates")
    for template in templates:
        where = f"announcements.yaml:{template.get('key')}"
        if not template.get("key"):
            raise LintError("announcements.yaml: every template needs a key")
        if template.get("level") not in ("info", "warning", "urgent"):
            raise LintError(f"{where}: level must be info, warning or urgent")
        require_bilingual(template.get("text"), f"{where}.text")


def lint_event(event: dict) -> None:
    for key in ("event", "venue", "wifi", "links", "phases"):
        if key not in event:
            raise LintError(f"event.yaml: missing top-level key {key!r}")
    for key in ("event", "venue", "wifi", "links"):
        if not isinstance(event[key], dict):
            raise LintError(f"event.yaml: {key} must be a mapping")
    for phase in require_mappings(event["phases"], "event.yaml:phases"):
        if not phase.get("key"):
            raise LintError("event.yaml: every phase needs a key")
        where = f"event.yaml:phases.{phase['key']}"
        require_time(phase.get("starts"), f"{where}.starts")
        require_day_offset(phase.get("day_offset", 0), where)
        require_bilingual({"hu": phase.get("hu"), "en": phase.get("en")}, where)


def lint_games(games: dict) -> None:
    seen: set[str] = set()
    for game in require_mappings(games.get("games", []), "games.yaml:games"):
        slug = game.get("slug")
        if not slug or slug in seen:
            raise LintError(f"games.yaml: slug missing or duplicated: {slug!r}")
        seen.add(slug)
        if not game.get("name"):
            raise LintError(f"games.yaml:{slug}: name is required")


def lint_all(event: dict, slides: dict, schedule: dict, games: dict, announcements: dict) -> None:
    lint_event(event)
    lint_games(games)
    lint_slides(slides, (phase["key"] for phase in event["phases"]))
    lint_schedule(schedule, (game["slug"] for game in games["games"]))
    lint_announcements(announcements)
