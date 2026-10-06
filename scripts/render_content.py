#!/usr/bin/env python3
"""Render docs/content.md from the YAML files under content/ and lint them.

Usage:
    python3 scripts/render_content.py            # write docs/content.md
    python3 scripts/render_content.py --check    # fail if docs/content.md is stale

The script also enforces the prose rules shared by the Ctrl-Alt-GG repos:
every bilingual string needs both `hu` and `en`, and no file under content/
may contain em dashes, en dashes, the ellipsis character, curly quotes or
non-breaking spaces. It exits non-zero on the first violation so CI can run it.

Only PyYAML is required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
OUTPUT = ROOT / "docs" / "content.md"

BANNED = {
    "–": "en dash",
    "—": "em dash",
    "…": "ellipsis character",
    "‘": "curly quote",
    "’": "curly quote",
    "“": "curly quote",
    "”": "curly quote",
    " ": "non-breaking space",
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
LANGS = ("hu", "en")


class LintError(Exception):
    pass


def load(name: str) -> dict:
    path = CONTENT / name
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def lint_glyphs() -> None:
    for path in sorted(CONTENT.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for glyph, label in BANNED.items():
                if glyph in line:
                    raise LintError(f"{path.relative_to(ROOT)}:{lineno}: {label} found")


def require_bilingual(value: object, where: str) -> dict:
    if not isinstance(value, dict):
        raise LintError(f"{where}: expected a mapping with hu and en")
    for lang in LANGS:
        if not isinstance(value.get(lang), str) or not value[lang].strip():
            raise LintError(f"{where}: missing or empty '{lang}'")
    return value


def lint_slides(slides: dict, phases: set[str]) -> None:
    seen: set[str] = set()
    for slide in slides["slides"]:
        sid = slide.get("id")
        if not sid or sid in seen:
            raise LintError(f"slide id missing or duplicated: {sid!r}")
        seen.add(sid)
        where = f"slides.yaml:{sid}"
        if slide.get("layout") not in LAYOUTS:
            raise LintError(f"{where}: unknown layout {slide.get('layout')!r}")
        slide_phases = slide.get("phases")
        if slide_phases != "all":
            if not isinstance(slide_phases, list) or not slide_phases:
                raise LintError(f"{where}: phases must be 'all' or a non-empty list")
            unknown = set(slide_phases) - phases
            if unknown:
                raise LintError(f"{where}: unknown phases {sorted(unknown)}")
        if slide.get("bilingual_mode", "alternate") not in ("alternate", "stacked"):
            raise LintError(f"{where}: bilingual_mode must be alternate or stacked")
        for key in ("kicker", "title", "body", "footer", "empty"):
            if key in slide:
                require_bilingual(slide[key], f"{where}.{key}")
        if "title" not in slide:
            raise LintError(f"{where}: title is required")
        for index, item in enumerate(slide.get("items", [])):
            require_bilingual(item, f"{where}.items[{index}]")
        if len(slide.get("items", [])) > 6:
            raise LintError(f"{where}: at most 6 items are shown on one slide")
        for cindex, column in enumerate(slide.get("columns", [])):
            require_bilingual(column.get("title"), f"{where}.columns[{cindex}].title")
            for index, item in enumerate(column.get("items", [])):
                require_bilingual(item, f"{where}.columns[{cindex}].items[{index}]")
        if slide.get("layout") == "split" and len(slide.get("columns", [])) != 2:
            raise LintError(f"{where}: split layout needs exactly two columns")
        link = slide.get("link")
        if link and "label" in link:
            require_bilingual(link["label"], f"{where}.link.label")


def lint_schedule(schedule: dict, games: set[str]) -> None:
    for index, entry in enumerate(schedule["entries"]):
        where = f"schedule.yaml:entries[{index}]"
        if entry.get("type") not in ("play", "break", "highlight"):
            raise LintError(f"{where}: type must be play, break or highlight")
        require_bilingual(entry.get("title"), f"{where}.title")
        if "note" in entry:
            require_bilingual(entry["note"], f"{where}.note")
        if entry.get("game") and entry["game"] not in games:
            raise LintError(f"{where}: unknown game slug {entry['game']!r}")


def lint_announcements(announcements: dict) -> None:
    for template in announcements["templates"]:
        where = f"announcements.yaml:{template.get('key')}"
        if template.get("level") not in ("info", "warning", "urgent"):
            raise LintError(f"{where}: level must be info, warning or urgent")
        require_bilingual(template.get("text"), f"{where}.text")


def md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def render_bilingual_block(slide: dict, lang: str) -> list[str]:
    lines: list[str] = []
    if "kicker" in slide:
        lines.append(f"- Kicker: {slide['kicker'][lang]}")
    lines.append(f"- Title: **{slide['title'][lang]}**")
    if "body" in slide:
        lines.append(f"- Body: {slide['body'][lang]}")
    if slide.get("items"):
        lines.append("- Items:")
        for item in slide["items"]:
            lines.append(f"  1. {item[lang]}")
    if slide.get("columns"):
        for column in slide["columns"]:
            lines.append(f"- Column **{column['title'][lang]}**:")
            for item in column["items"]:
                lines.append(f"  1. {item[lang]}")
    if slide.get("columns_labels"):
        labels = ", ".join(v[lang] for v in slide["columns_labels"].values())
        lines.append(f"- Column labels: {labels}")
    if slide.get("sections"):
        labels = ", ".join(v[lang] for v in slide["sections"].values())
        lines.append(f"- Section labels: {labels}")
    if "empty" in slide:
        lines.append(f"- Empty state: {slide['empty'][lang]}")
    if "footer" in slide:
        lines.append(f"- Footer: {slide['footer'][lang]}")
    link = slide.get("link")
    if link:
        label = link.get("label", {}).get(lang)
        qr = " (QR code)" if link.get("qr") else ""
        target = link["url"]
        lines.append(f"- Link: {label + ': ' if label else ''}{target}{qr}")
    return lines


def render(event: dict, slides: dict, schedule: dict, announcements: dict) -> str:
    defaults = slides.get("defaults", {})
    out: list[str] = []
    out.append("# Signage content")
    out.append("")
    out.append(
        "<!-- Generated by scripts/render_content.py from content/*.yaml. "
        "Do not edit by hand; edit the YAML and re-run the script. -->"
    )
    out.append("")
    out.append(
        "This is the text that goes on the screens, rendered in a readable form from "
        "the YAML files under `content/`. The YAML is the source of truth and is what "
        "`manage.py loadcontent` imports. Layout names refer to `docs/design.md`, the "
        "phase names to `content/event.yaml`."
    )
    out.append("")
    out.append("## How the rotation works")
    out.append("")
    out.append(
        "- Every slide exists in Hungarian and English. In `alternate` mode the player shows "
        "the Hungarian pass, then the English pass, each for `duration_seconds`. In `stacked` "
        "mode both languages share one pass, Hungarian large and English beneath."
    )
    out.append(
        "- A slide is in rotation only while the event is in one of its `phases`. The "
        "organizer sets the phase in the admin, or lets the clock pick it."
    )
    out.append(
        "- Inside one cycle slides are ordered by `priority` (high first), then by the order "
        "in this file. Live slides re-render on every bundle refresh."
    )
    out.append(
        "- Strings in `{braces}` are placeholders filled from the Event model at render time."
    )
    out.append("")
    out.append("## Rotation at a glance")
    out.append("")
    out.append("| Slide | Layout | Source | Phases | Seconds | Mode | Priority |")
    out.append("|---|---|---|---|---|---|---|")
    for slide in slides["slides"]:
        phases = slide["phases"]
        phases_text = "all" if phases == "all" else ", ".join(phases)
        out.append(
            "| `{id}` | {layout} | {source} | {phases} | {dur} | {mode} | {prio} |".format(
                id=slide["id"],
                layout=slide["layout"],
                source=slide.get("source", "static"),
                phases=phases_text,
                dur=slide.get("duration_seconds", defaults.get("duration_seconds")),
                mode=slide.get("bilingual_mode", defaults.get("bilingual_mode")),
                prio=slide.get("priority", defaults.get("priority")),
            )
        )
    out.append("")
    out.append("## Slides")
    out.append("")
    for slide in slides["slides"]:
        out.append(f"### `{slide['id']}`")
        out.append("")
        phases = slide["phases"]
        phases_text = "all" if phases == "all" else ", ".join(phases)
        out.append(
            f"Layout `{slide['layout']}`, source `{slide.get('source', 'static')}`, "
            f"phases: {phases_text}."
        )
        if slide.get("notes"):
            out.append("")
            out.append(f"> {slide['notes'].strip()}")
        out.append("")
        out.append("**Magyar**")
        out.append("")
        out.extend(render_bilingual_block(slide, "hu"))
        out.append("")
        out.append("**English**")
        out.append("")
        out.extend(render_bilingual_block(slide, "en"))
        out.append("")
    out.append("## Schedule")
    out.append("")
    out.append(
        "Copied from the homepage schedule page. `day_offset` 1 means after midnight. "
        "Every schedule slide carries the guideline disclaimer."
    )
    out.append("")
    out.append("| Time | Type | Game | Magyar | English |")
    out.append("|---|---|---|---|---|")
    for entry in schedule["entries"]:
        time = entry["time"] + (" (+1)" if entry.get("day_offset") else "")
        hu = entry["title"]["hu"]
        en = entry["title"]["en"]
        if "note" in entry:
            hu += f" ({entry['note']['hu']})"
            en += f" ({entry['note']['en']})"
        out.append(
            f"| {time} | {entry['type']} | {md_escape(entry.get('label') or '')} | "
            f"{md_escape(hu)} | {md_escape(en)} |"
        )
    out.append("")
    out.append("## Announcement templates")
    out.append("")
    out.append(
        "Organizers activate these from the admin, filling the `{placeholders}`. "
        "`takeover` announcements replace the rotation while active; the others render "
        "as a bar at the bottom of the safe area."
    )
    out.append("")
    out.append("| Key | Level | Takeover | Magyar | English |")
    out.append("|---|---|---|---|---|")
    for template in announcements["templates"]:
        out.append(
            f"| `{template['key']}` | {template['level']} | "
            f"{'yes' if template.get('takeover') else 'no'} | "
            f"{md_escape(template['text']['hu'])} | {md_escape(template['text']['en'])} |"
        )
    out.append("")
    out.append("## Event facts used by placeholders")
    out.append("")
    ev = event["event"]
    venue = event["venue"]
    wifi = event["wifi"]
    out.append(f"- Event: {ev['name']}, tagline \"{ev['tagline']}\"")
    out.append(f"- Starts: {ev['starts_at']} ({ev['timezone']}), ends: {ev['ends_at']}")
    out.append(f"- Venue: {venue['name']}, {venue['address']}")
    out.append(f"- Entrance: {venue['entrance_note']['hu']} / {venue['entrance_note']['en']}")
    out.append(f"- Parking: {venue['parking']['hu']} / {venue['parking']['en']}")
    out.append(
        f"- Assembly point: {venue['assembly_point']['hu']} / {venue['assembly_point']['en']}"
    )
    out.append(f"- Wi-Fi SSID: {wifi['ssid']}, password: {wifi['password']}")
    out.append(f"- Organizers: {', '.join(event['organizers'])}")
    out.append(f"- Email: {event['links']['email']}")
    out.append("")
    out.append("### Links")
    out.append("")
    for key, url in event["links"].items():
        out.append(f"- {key}: {url}")
    out.append("")
    out.append("### Public transport")
    out.append("")
    out.append("| Mode | Stop | Distance | Lines | Night lines |")
    out.append("|---|---|---|---|---|")
    for stop in venue["transit"]:
        out.append(
            f"| {stop['mode']} | {stop['stop']} | {stop['distance_m']} m | "
            f"{', '.join(stop['lines']) or '-'} | {', '.join(stop['night_lines']) or '-'} |"
        )
    out.append("")
    out.append("### Phases")
    out.append("")
    out.append("| Key | Magyar | English | Starts |")
    out.append("|---|---|---|---|")
    for phase in event["phases"]:
        starts = phase["starts"] + (" (+1)" if phase.get("day_offset") else "")
        out.append(f"| `{phase['key']}` | {phase['hu']} | {phase['en']} | {starts} |")
    out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    try:
        lint_glyphs()
        event = load("event.yaml")
        slides = load("slides.yaml")
        schedule = load("schedule.yaml")
        games = load("games.yaml")
        announcements = load("announcements.yaml")
        phases = {phase["key"] for phase in event["phases"]}
        lint_slides(slides, phases)
        lint_schedule(schedule, {game["slug"] for game in games["games"]})
        lint_announcements(announcements)
    except LintError as error:
        print(f"lint error: {error}", file=sys.stderr)
        return 1
    rendered = render(event, slides, schedule, announcements)
    if check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            print("docs/content.md is stale; run scripts/render_content.py", file=sys.stderr)
            return 1
        print("docs/content.md is up to date")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(rendered.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
