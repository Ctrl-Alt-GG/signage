"""Validation rules for content/*.yaml. Pure functions, no Django imports, so
scripts/render_content.py can use them without the application installed."""

from __future__ import annotations

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


class LintError(Exception):
    pass


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
    for slide in slides.get("slides", []):
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
                require_bilingual(slide[key], f"{where}.{key}")
        items = slide.get("items", [])
        if len(items) > MAX_ITEMS:
            raise LintError(f"{where}: at most {MAX_ITEMS} items are shown on one slide")
        for index, item in enumerate(items):
            require_bilingual(item, f"{where}.items[{index}]")
        columns = slide.get("columns", [])
        if slide.get("layout") == "split" and len(columns) != 2:
            raise LintError(f"{where}: split layout needs exactly two columns")
        for cindex, column in enumerate(columns):
            require_bilingual(column.get("title"), f"{where}.columns[{cindex}].title")
            for index, item in enumerate(column.get("items", [])):
                require_bilingual(item, f"{where}.columns[{cindex}].items[{index}]")
        for group in ("columns_labels", "sections"):
            for key, value in (slide.get(group) or {}).items():
                require_bilingual(value, f"{where}.{group}.{key}")
        link = slide.get("link")
        if link and "label" in link:
            require_bilingual(link["label"], f"{where}.link.label")


def lint_schedule(schedule: dict, games: Iterable[str]) -> None:
    game_slugs = set(games)
    for index, entry in enumerate(schedule.get("entries", [])):
        where = f"schedule.yaml:entries[{index}]"
        if entry.get("type") not in ("play", "break", "highlight"):
            raise LintError(f"{where}: type must be play, break or highlight")
        require_bilingual(entry.get("title"), f"{where}.title")
        if "note" in entry:
            require_bilingual(entry["note"], f"{where}.note")
        if entry.get("game") and entry["game"] not in game_slugs:
            raise LintError(f"{where}: unknown game slug {entry['game']!r}")


def lint_announcements(announcements: dict) -> None:
    for template in announcements.get("templates", []):
        where = f"announcements.yaml:{template.get('key')}"
        if template.get("level") not in ("info", "warning", "urgent"):
            raise LintError(f"{where}: level must be info, warning or urgent")
        require_bilingual(template.get("text"), f"{where}.text")


def lint_event(event: dict) -> None:
    for key in ("event", "venue", "wifi", "links", "phases"):
        if key not in event:
            raise LintError(f"event.yaml: missing top-level key {key!r}")
    for phase in event["phases"]:
        if not phase.get("key") or not phase.get("starts"):
            raise LintError("event.yaml: every phase needs key and starts")
        require_bilingual({"hu": phase.get("hu"), "en": phase.get("en")}, "event.yaml.phases")


def lint_games(games: dict) -> None:
    seen: set[str] = set()
    for game in games.get("games", []):
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
