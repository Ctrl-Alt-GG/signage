#!/usr/bin/env python3
"""Screenshot every slide in both languages and every announcement, and check the
safe-area rules.

Usage (with the Django server running and the frontend built):
    uv run python scripts/screenshots.py --base-url http://localhost:4173

Writes screenshots/<slide>-<lang>.png and screenshots/announcement-<name>.png (git-ignored)
and exits non-zero when any visible text lies outside the content-safe area, is cut off by
its box, or a slide overflows its box.

Live slides are shown with live data as full as their layouts take: long lists of servers,
matches and streams, the schedule from content/schedule.yaml at its busiest slot, and a
countdown of days. Streams slides are also shown in the state where Streams can't tell
which channels are live.

Announcements are checked with every template of content/announcements.yaml filled in with
values of a realistic length, and with texts as long as the admin accepts.

Live data and announcements are put into the answer the display gets from the backend, so
nothing is written to the database and no upstream system is needed.
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from datetime import UTC, datetime, timedelta
from itertools import groupby
from pathlib import Path

import yaml
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SAFE = {"left": 96, "top": 204, "right": 1824, "bottom": 768}
TOLERANCE = 2

# What the admin asks for when an announcement is published from a template, at lengths
# an organizer would type.
SAMPLE_VALUES = {
    "team_a": "Clutch Kings",
    "team_b": "Eco Round Enjoyers",
    "minutes": "10",
    "game": "Counter-Strike 2",
    "time": "21:30",
    "until": "19:00",
    "deadline": "18:30",
    "area": "a színpad melletti asztalsor",
    "from": "22:00",
    "to": "22:30",
    "issue": "a Minecraft szerver újraindul",
    "workaround": "várj két percet, majd csatlakozz újra",
    "item": "fekete Logitech egér, piros alátéttel",
    "assembly_point": "a Nagymihály utcai parkoló, a lépcsővel szemben",
}
# As long as the admin lets an announcement be, in both languages.
LONGEST = {
    "hu": ("Hagyd el az épületet a legközelebbi kijáraton, a géped marad. " * 5)[:300].strip(),
    "en": ("Leave the building through the nearest exit and leave your PC. " * 5)[:300].strip(),
}
# The bar shows a long text one language at a time and switches after this long.
BAR_PAGE_MS = 8_000
BUNDLE_ROUTE = "**/api/v1/screens/*/bundle/**"

TEAMS = [
    "Clutch Kings",
    "Eco Round Enjoyers",
    "Óbudai Headshot Egylet",
    "Ninjas in Pyjamas Fan Club",
    "Rush B No Stop",
    "Flashbang Felelősök",
    "Lan Party Veterans",
    "Kockafej Kollektíva",
]
CHANNELS = [
    ("Main stage: CS2 tournament", False),
    ("Minecraft build-off", False),
    ("Casters' desk", True),
    ("OpenTTD rail network", False),
    ("Retro corner", False),
    ("Night shift radio", True),
]

CHECK_JS = """
({safe, tolerance, within}) => {
  const stage = document.querySelector('[data-stage]');
  const area = document.querySelector('[data-safe-area]');
  if (!stage || !area) return {errors: ['stage or safe area missing']};
  const root = within ? area.querySelector(within) : area;
  if (!root) return {errors: [`${within} is not on the screen`]};
  const stageRect = stage.getBoundingClientRect();
  const errors = [];
  const clipsOverflow = (value) => ['hidden', 'clip', 'auto', 'scroll'].includes(value);
  // Visible text is what matters: intersect each text rect with every clipping ancestor.
  const clipRect = (node) => {
    let rect = {left: -Infinity, top: -Infinity, right: Infinity, bottom: Infinity};
    for (let el = node.parentElement; el && el !== area.parentElement; el = el.parentElement) {
      const style = getComputedStyle(el);
      const clamped = style.webkitLineClamp && style.webkitLineClamp !== 'none';
      if (clipsOverflow(style.overflowX) || clipsOverflow(style.overflowY) || clamped) {
        const box = el.getBoundingClientRect();
        rect = {
          left: Math.max(rect.left, box.left), top: Math.max(rect.top, box.top),
          right: Math.min(rect.right, box.right), bottom: Math.min(rect.bottom, box.bottom),
        };
      }
    }
    return rect;
  };
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim()) continue;
    const clip = clipRect(node);
    const allowClip = Boolean(node.parentElement.closest('[data-allow-clip]'));
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const rect of range.getClientRects()) {
      const left = Math.max(rect.left, clip.left), top = Math.max(rect.top, clip.top);
      const right = Math.min(rect.right, clip.right), bottom = Math.min(rect.bottom, clip.bottom);
      const clippedBy = Math.max(clip.left - rect.left, clip.top - rect.top,
                                 rect.right - clip.right, rect.bottom - clip.bottom);
      if (clippedBy > tolerance && !allowClip) {
        const snippet = node.textContent.trim().slice(0, 40);
        errors.push(`text clipped by its box: "${snippet}" (${Math.round(clippedBy)}px)`);
      }
      if (right - left <= 1 || bottom - top <= 1) continue;
      const x1 = left - stageRect.left, y1 = top - stageRect.top;
      const x2 = right - stageRect.left, y2 = bottom - stageRect.top;
      if (x1 < safe.left - tolerance || y1 < safe.top - tolerance ||
          x2 > safe.right + tolerance || y2 > safe.bottom + tolerance) {
        const snippet = node.textContent.trim().slice(0, 40);
        const box = [x1, y1, x2, y2].map(Math.round).join(',');
        errors.push(`text outside safe area: "${snippet}" at ${box}`);
      }
    }
  }
  const slide = within ? null : area.querySelector('[data-slide]');
  if (slide && slide.scrollHeight > slide.clientHeight + tolerance) {
    errors.push(`slide overflows by ${slide.scrollHeight - slide.clientHeight}px`);
  }
  // A card taller than its grid runs into what comes after the grid, such as the footer,
  // with none of its own text cut off.
  for (const grid of slide ? slide.querySelectorAll('*') : []) {
    if (getComputedStyle(grid).display !== 'grid') continue;
    const bottom = grid.getBoundingClientRect().bottom;
    for (const cell of grid.children) {
      const over = cell.getBoundingClientRect().bottom - bottom;
      if (over > tolerance) {
        const snippet = cell.textContent.trim().slice(0, 40);
        errors.push(`box taller than its grid: "${snippet}" (${Math.round(over)}px)`);
      }
    }
  }
  return {errors};
}
"""


def chromium_path() -> str | None:
    candidates = glob.glob("/opt/pw-browsers/chromium*/chrome-linux*/chrome") + glob.glob(
        "/opt/pw-browsers/chromium"
    )
    return candidates[0] if candidates else None


def announcement_cases() -> list[dict]:
    """One announcement per template, filled in, and the longest a bar and a takeover can
    be asked to show."""
    with (ROOT / "content" / "announcements.yaml").open(encoding="utf-8") as handle:
        templates = yaml.safe_load(handle)["templates"]

    def fill(text: str) -> str:
        return re.sub(r"\{([a-z][a-z0-9_]*)\}", lambda m: SAMPLE_VALUES.get(m[1], m[1]), text)

    cases = [
        {
            "name": template["key"],
            "level": template["level"],
            "takeover": bool(template.get("takeover", False)),
            "text": {lang: fill(template["text"][lang]) for lang in ("hu", "en")},
        }
        for template in templates
    ]
    for takeover in (True, False):
        cases.append(
            {
                "name": f"longest-{'takeover' if takeover else 'bar'}",
                "level": "urgent" if takeover else "warning",
                "takeover": takeover,
                "text": LONGEST,
            }
        )
    return cases


def _load(name: str) -> dict:
    with (ROOT / "content" / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _schedule_sample() -> dict:
    """The schedule of content/schedule.yaml with "now" at its busiest slot."""
    games = {
        game["slug"]: {
            "slug": game["slug"],
            "name": game["name"],
            "short": game["short"],
            "color_bg": game["color"]["bg"],
            "color_text": game["color"]["text"],
        }
        for game in _load("games.yaml")["games"]
    }
    starts = datetime.fromisoformat(_load("event.yaml")["event"]["starts_at"])
    empty = {"hu": "", "en": ""}
    views = [
        {
            "time": entry["time"],
            "type": entry["type"],
            "label": entry.get("label", ""),
            "title": entry["title"],
            "note": entry.get("note") or empty,
            "game": games.get(entry.get("game") or ""),
            "starts_at": datetime.combine(
                starts.date() + timedelta(days=entry["day_offset"]),
                datetime.strptime(entry["time"], "%H:%M").time(),
                starts.tzinfo,
            ).isoformat(),
        }
        for entry in _load("schedule.yaml")["entries"]
    ]
    slots = [list(group) for _, group in groupby(views, key=lambda view: view["starts_at"])]
    busiest = max(range(len(slots)), key=lambda index: len(slots[index]))
    return {
        "now": slots[busiest],
        "next": slots[busiest + 1] if busiest + 1 < len(slots) else [],
        "later": [view for slot in slots[busiest + 2 :] for view in slot],
        "upcoming": [view for slot in slots[busiest:] for view in slot],
    }


def _match(number: int, status: str) -> dict:
    return {
        "id": number,
        "team1": TEAMS[number % len(TEAMS)],
        "team2": TEAMS[(number + 3) % len(TEAMS)],
        "score1": 13 if status == "finished" else number % 9,
        "score2": 11 if status == "finished" else 7,
        "start_local": f"{20 + number // 4}:{number % 4 * 15:02d}",
        "round": "Upper bracket semi-final",
        "status": status,
    }


def live_samples() -> dict[str, dict]:
    """Live data of each source with as much in it as its layout shows, and more."""
    servers = [
        {
            "name": f"Ctrl-Alt-GG {game['name']} #{number}",
            "info": "",
            "game_slug": game["slug"],
            "game_name": game["name"],
            "game_short": game["short"],
            "color_bg": game["color"]["bg"],
            "color_text": game["color"]["text"],
            "players_text": f"{number + 9}/{number + 24}",
        }
        for number, game in enumerate(_load("games.yaml")["games"][:12], start=1)
    ]
    channels = [
        {
            "id": f"channel-{number}",
            "name": name,
            "audio_only": audio_only,
            "thumbnail_url": "",
            "watch_url": "",
        }
        for number, (name, audio_only) in enumerate(CHANNELS, start=1)
    ]
    return {
        "live:clock": {
            "target": (datetime.now(UTC) + timedelta(days=3, hours=4)).isoformat(),
            "passed": False,
        },
        "live:schedule": _schedule_sample(),
        "live:projectile": {"servers": servers, "stale": False},
        "live:bracket": {
            "id": 1,
            "name": "Ctrl-Alt-GG CS2 Cup",
            "live": [_match(1, "live"), _match(2, "awaiting")],
            "live_page": {"number": 1, "count": 2, "first": 1, "last": 2, "total": 4},
            "upcoming": [_match(number, "scheduled") for number in range(3, 9)],
            "results": [_match(number, "finished") for number in range(9, 14)],
            "stale": False,
        },
        "live:streams": {
            "live": channels,
            "source_status": "fresh",
            "observed_at": datetime.now(UTC).isoformat(),
            "age_seconds": 2.0,
            "stale": False,
        },
    }


# Other states a live slide has, shot as <slide>-<state>-<lang>.png.
LIVE_STATES = {
    "live:streams": {
        "unavailable": {"live": [], "source_status": "unavailable", "stale": True},
    },
}


def check_announcements(page, args, out: Path, failures: list[str]) -> int:
    """Show each announcement on a screen and check that all of its text can be read."""
    cases = announcement_cases()
    current: dict = {}

    def with_announcement(route):
        response = route.fetch()
        bundle = response.json()
        bundle["announcements"] = [{"id": current["name"], "ends_at": None, **current}]
        bundle["announcements"][0].pop("name")
        route.fulfill(response=response, json=bundle)

    page.route(BUNDLE_ROUTE, with_announcement)
    # Any slide will do behind a bar; a preview keeps it from changing meanwhile.
    url = f"{args.base_url}/display/{args.screen}/?preview={args.announcement_slide}&lang=hu"
    for case in cases:
        current.clear()
        current.update(case)
        selector = (
            '[data-chrome="takeover"]' if case["takeover"] else '[data-chrome="announcement"]'
        )
        page.goto(url, wait_until="networkidle")
        try:
            page.wait_for_selector(selector, timeout=10_000)
        except PlaywrightError:
            failures.append(f"announcement {case['name']}: not shown")
            continue
        page.evaluate("document.fonts.ready")
        # A long text in the bar comes one language after the other.
        paged = not case["takeover"] and max(map(len, case["text"].values())) > 70
        for part in ("hu", "en") if paged else ("",):
            page.wait_for_timeout(600 if part in ("", "hu") else BAR_PAGE_MS)
            suffix = f"-{part}" if part else ""
            page.screenshot(path=str(out / f"announcement-{case['name']}{suffix}.png"))
            result = page.evaluate(
                CHECK_JS, {"safe": SAFE, "tolerance": TOLERANCE, "within": selector}
            )
            shown = page.inner_text(selector)
            wanted = [case["text"][part]] if part else list(case["text"].values())
            for text in wanted:
                if text not in shown:
                    failures.append(f"announcement {case['name']}{suffix}: text is not all shown")
            for error in result["errors"]:
                failures.append(f"announcement {case['name']}{suffix}: {error}")
    page.unroute(BUNDLE_ROUTE)
    return len(cases)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:4173")
    parser.add_argument("--screen", default="main")
    parser.add_argument("--out", default=str(ROOT / "screenshots"))
    parser.add_argument(
        "--slides", nargs="*", help="Slide keys; default: all in content/slides.yaml"
    )
    parser.add_argument("--langs", default="hu,en")
    parser.add_argument("--chromium", help="Path to a Chromium to use instead of Playwright's.")
    parser.add_argument(
        "--announcement-slide",
        default="house_rules",
        help="The slide shown behind the announcements.",
    )
    parser.add_argument("--skip-announcements", action="store_true", help="Only check the slides.")
    args = parser.parse_args()

    with (ROOT / "content" / "slides.yaml").open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    default_mode = document.get("defaults", {}).get("bilingual_mode", "alternate")
    modes = {s["id"]: s.get("bilingual_mode", default_mode) for s in document["slides"]}
    sources = {s["id"]: s.get("source", "static") for s in document["slides"]}
    slides = args.slides or list(modes)
    samples = live_samples()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    announcements = 0
    with sync_playwright() as playwright:
        launch_kwargs: dict = {"executable_path": args.chromium} if args.chromium else {}
        try:
            browser = playwright.chromium.launch(**launch_kwargs)
        except PlaywrightError:
            path = chromium_path()
            if not path or args.chromium:
                raise
            browser = playwright.chromium.launch(executable_path=path)
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        live: dict = {}

        def with_live(route):
            response = route.fetch()
            bundle = response.json()
            for pass_ in bundle["passes"]:
                if pass_["source"] in live:
                    pass_["live"] = live[pass_["source"]]
            route.fulfill(response=response, json=bundle)

        page.route(BUNDLE_ROUTE, with_live)
        for slide in slides:
            source = sources.get(slide, "static")
            states = {"": samples.get(source), **LIVE_STATES.get(source, {})}
            # Stacked slides show both languages on one pass, so shoot that pass instead.
            langs = ["both"] if modes.get(slide) == "stacked" else args.langs.split(",")
            for state, data in states.items():
                live.clear()
                if data is not None:
                    live[source] = data
                name = f"{slide}-{state}" if state else slide
                for lang in langs:
                    url = f"{args.base_url}/display/{args.screen}/?preview={slide}&lang={lang}"
                    page.goto(url, wait_until="networkidle")
                    try:
                        page.wait_for_selector("[data-slide]", timeout=10_000)
                    except PlaywrightError:
                        failures.append(f"{name}/{lang}: no slide rendered")
                        page.screenshot(path=str(out / f"{name}-{lang}.png"))
                        continue
                    page.evaluate("document.fonts.ready")
                    page.wait_for_timeout(600)
                    page.screenshot(path=str(out / f"{name}-{lang}.png"))
                    result = page.evaluate(
                        CHECK_JS, {"safe": SAFE, "tolerance": TOLERANCE, "within": None}
                    )
                    for error in result["errors"]:
                        failures.append(f"{name}/{lang}: {error}")
        page.unroute(BUNDLE_ROUTE)
        if not args.skip_announcements:
            announcements = check_announcements(page, args, out, failures)
        browser.close()

    print(
        f"screenshots for {len(slides)} slides and {announcements} announcements written to {out}"
    )
    for failure in failures:
        print("FAIL", failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
