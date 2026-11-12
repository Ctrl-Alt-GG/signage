"""Build the JSON bundle a screen polls: the slides in rotation, expanded into language
passes, plus the active announcements, the phase and the clock."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from signage.integrations.bracket import BracketClient
from signage.integrations.projectile import ProjectileClient
from signage.integrations.streams import StreamsClient
from signage.models import (
    LANGS,
    Announcement,
    DisplaySettings,
    Event,
    Integration,
    Phase,
    Screen,
    Slide,
)
from signage.rendering.phases import resolve_phase
from signage.rendering.placeholders import UnresolvedPlaceholderError, resolve
from signage.rendering.schedule import build_schedule_view

log = logging.getLogger(__name__)

LIVE_CLIENTS = {
    Slide.Source.PROJECTILE: ProjectileClient,
    Slide.Source.BRACKET: BracketClient,
    Slide.Source.STREAMS: StreamsClient,
}


def _wifi_payload(event: Event) -> str:
    def escape(value: str) -> str:
        for char in ("\\", ";", ",", ":", '"'):
            value = value.replace(char, f"\\{char}")
        return value

    if event.wifi_security == "nopass":
        return f"WIFI:T:nopass;S:{escape(event.wifi_ssid)};;"
    ssid, password = escape(event.wifi_ssid), escape(event.wifi_password)
    return f"WIFI:T:{event.wifi_security};S:{ssid};P:{password};;"


# What the event fills into {placeholders}, per language.
Values = dict[str, dict[str, str]]


def placeholder_values(event: Event) -> Values:
    return {lang: event.placeholder_values(lang) for lang in LANGS}


def _resolved_pair(slide: Slide, field: str, values: Values) -> dict[str, str]:
    return {lang: resolve(slide.text(field, lang), values[lang]) for lang in LANGS}


def _resolved_items(items, values: Values) -> list[dict[str, str]]:
    return [
        {
            "hu": resolve(item.text_hu, values["hu"]),
            "en": resolve(item.text_en, values["en"]),
            "icon": item.icon,
        }
        for item in items
    ]


def slide_content(slide: Slide, event: Event, values: Values | None = None) -> dict[str, Any]:
    values = values or placeholder_values(event)
    items = list(slide.items.all())
    content: dict[str, Any] = {
        "kicker": _resolved_pair(slide, "kicker", values),
        "title": _resolved_pair(slide, "title", values),
        "body": _resolved_pair(slide, "body", values),
        "footer": (
            {lang: "" for lang in LANGS}
            if slide.layout == Slide.Layout.CREDENTIALS
            else _resolved_pair(slide, "footer", values)
        ),
        "empty": _resolved_pair(slide, "empty", values),
        "items": _resolved_items([i for i in items if i.column == 1], values),
        "columns": [],
        "labels": slide.labels or {},
        "link": None,
        "wifi_credentials": None,
    }
    if slide.layout == Slide.Layout.CREDENTIALS:
        content["wifi_credentials"] = {
            "ssid": resolve("{wifi_ssid}", values["hu"]),
            "password": (
                None
                if event.wifi_security == "nopass"
                else resolve("{wifi_password}", values["hu"])
            ),
        }
    if slide.layout == Slide.Layout.SPLIT:
        content["columns"] = [
            {
                "title": _resolved_pair(slide, f"column{column}_title", values),
                "items": _resolved_items([i for i in items if i.column == column], values),
            }
            for column in (1, 2)
        ]
        content["items"] = []
    if slide.link_url or slide.link_qr:
        url = slide.link_url
        qr_payload = _wifi_payload(event) if url == "wifi" else url
        content["link"] = {
            "url": "" if url == "wifi" else url,
            "label": _resolved_pair(slide, "link_label", values),
            "qr_payload": qr_payload if slide.link_qr else "",
        }
    return content


def live_data(slide: Slide, event: Event, now: datetime, warnings: list[str]) -> dict | None:
    """Return the live view model for a slide, or None when the slide must be dropped."""
    if slide.source == Slide.Source.STATIC:
        return None
    if slide.source == Slide.Source.SCHEDULE:
        return build_schedule_view(event, now).as_dict()
    if slide.source == Slide.Source.CLOCK:
        if event.starts_at <= now:
            warnings.append(f"{slide.key}: countdown target has passed")
            return None
        return {"target": event.starts_at.isoformat(), "passed": False}
    client = LIVE_CLIENTS[slide.source]()
    if not client.enabled:
        warnings.append(f"{slide.key}: disabled, the {client.kind} integration is not configured")
        return None
    result = client.fetch()
    if result.data is None:
        return {"empty": True, "stale": True, "error": result.error}
    data = dict(result.data)
    # Stale when our transport cache is stale or when the upstream reports its own source
    # as stale (Streams does), so neither case shows as fresh.
    data["stale"] = bool(result.stale) or data.get("source_status") == "stale"
    if slide.source == Slide.Source.STREAMS:
        # The address of a thumbnail never changes, and a screen keeps every slide loaded,
        # so its browser would show the first frame for the rest of the day. The version
        # moves on whenever a newer frame can be had.
        version = int(now.timestamp() // settings.SIGNAGE_THUMBNAIL_CACHE_SECONDS)
        data["live"] = [
            {
                **channel,
                "thumbnail_url": (
                    reverse("signage-api:thumbnail", kwargs={"stream_id": channel["id"]})
                    + f"?v={version}"
                ),
            }
            for channel in data.get("live", [])
        ]
    return data


def select_slides(screen: Screen, phase: Phase | None, now: datetime) -> list[Slide]:
    queryset = Slide.objects.filter(enabled=True).prefetch_related("items", "phases")
    ordered = list(screen.slides.through.objects.filter(screen=screen).order_by("order"))
    if ordered:
        allowed = [row.slide_id for row in ordered]
        by_key = {slide.key: slide for slide in queryset.filter(pk__in=allowed)}
        candidates = [by_key[key] for key in allowed if key in by_key]
    else:
        candidates = list(queryset.order_by("-priority", "order", "key"))
    return [s for s in candidates if s.in_phase(phase) and s.is_valid_at(now)]


LEVEL_RANK = {"urgent": 0, "warning": 1, "info": 2}


def active_announcements(now: datetime) -> list[Announcement]:
    """Every announcement that is on at `now`, the most important first. Announcements that
    have ended stay in the database for the record; they are not loaded."""
    rows = list(
        Announcement.objects.filter(enabled=True, starts_at__lte=now)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .prefetch_related("screens")
    )
    # A takeover replaces the rotation, so it comes before a bar of the same level.
    rows.sort(key=lambda a: (LEVEL_RANK[a.level], not a.takeover, -a.created_at.timestamp()))
    return rows


def announcement_view(announcement: Announcement) -> dict[str, Any]:
    return {
        "id": str(announcement.pk),
        "level": announcement.level,
        "takeover": announcement.takeover,
        "text": announcement.pair("text"),
        "ends_at": announcement.ends_at.isoformat() if announcement.ends_at else None,
    }


def screen_announcements(screen: Screen, now: datetime) -> list[dict[str, Any]]:
    """What a screen announces: the announcements for every screen and those for this one,
    then the one mirrored from Projectile."""
    views = []
    for announcement in active_announcements(now):
        screens = announcement.screens.all()
        if not screens or any(candidate.pk == screen.pk for candidate in screens):
            views.append(announcement_view(announcement))
    if mirrored := _mirrored_announcement():
        views.append(mirrored)
    return views


def _mirrored_announcement() -> dict | None:
    config = Integration.objects.filter(kind=Integration.Kind.PROJECTILE).first()
    if not config or not config.mirror_announcement or not config.is_configured:
        return None
    result = ProjectileClient(config).fetch()
    text = (result.data or {}).get("announcement") or ""
    if not text:
        return None
    return {
        "id": "projectile",
        "level": "info",
        "takeover": False,
        "text": {"hu": text, "en": text},
        "ends_at": None,
    }


def _passes_for(
    slide: Slide,
    screen: Screen,
    content: dict,
    live: dict | None,
    preview_lang: str | None = None,
) -> list[dict]:
    duration_ms = slide.duration_seconds * 1000
    base = {
        "slide": slide.key,
        "layout": slide.layout,
        "source": slide.source,
        "duration_ms": duration_ms,
        "content": content,
        "live": live,
    }
    if preview_lang in (*LANGS, "both"):
        langs = [preview_lang]
    elif screen.language_mode in LANGS:
        langs = [screen.language_mode]
    elif slide.bilingual_mode == Slide.BilingualMode.STACKED:
        langs = ["both"]
    else:
        langs = list(LANGS)

    # Pages are ordinary consecutive passes, so the carousel shows every live match
    # during one rotation. Hidden, mounted slides need no timer of their own.
    matches = live.get("live", []) if live and slide.layout == Slide.Layout.TOURNAMENT else []
    page_size = 2
    page_count = max(1, (len(matches) + page_size - 1) // page_size)
    passes = []
    for page in range(page_count):
        first = page * page_size
        page_live = live
        if matches:
            page_live = {
                **live,
                "live": matches[first : first + page_size],
                "live_page": {
                    "number": page + 1,
                    "count": page_count,
                    "first": first + 1,
                    "last": min(first + page_size, len(matches)),
                    "total": len(matches),
                },
            }
        suffix = f":page-{page + 1}" if page_count > 1 else ""
        for lang in langs:
            passes.append(
                {**base, "live": page_live, "key": f"{slide.key}:{lang}{suffix}", "lang": lang}
            )
    return passes


def build_bundle(
    screen: Screen,
    now: datetime,
    *,
    preview_slide: str | None = None,
    preview_lang: str | None = None,
    phase_override: str | None = None,
) -> dict[str, Any]:
    event = Event.get_solo()
    warnings: list[str] = []
    phase = resolve_phase(event, now)
    if phase_override:
        phase = Phase.objects.filter(key=phase_override).first() or phase

    if preview_slide:
        slides = list(Slide.objects.filter(pk=preview_slide).prefetch_related("items"))
    else:
        slides = select_slides(screen, phase, now)

    values = placeholder_values(event)
    passes: list[dict] = []
    for slide in slides:
        live = live_data(slide, event, now, warnings)
        if slide.is_live and live is None and not preview_slide:
            continue
        try:
            content = slide_content(slide, event, values)
        except UnresolvedPlaceholderError as error:
            warnings.append(f"{slide.key}: unresolved placeholder {error.name}")
            if not preview_slide:
                continue
            content = {"title": slide.pair("title"), "items": [], "columns": [], "labels": {}}
        slide_passes = _passes_for(
            slide, screen, content, live, preview_lang if preview_slide else None
        )
        passes.extend(slide_passes)

    announcements = [] if preview_slide else screen_announcements(screen, now)

    display = DisplaySettings.get_solo()
    return {
        "generated_at": now.astimezone(event.tz).isoformat(),
        "screen": {
            "slug": screen.slug,
            "name": screen.name,
            "refresh_seconds": screen.refresh_seconds,
            "show_clock": screen.show_clock,
            "show_progress": screen.show_progress,
            "language_mode": screen.language_mode,
        },
        "phase": {"key": phase.key, "name": phase.pair("name")} if phase else None,
        "clock": {"now": now.astimezone(event.tz).isoformat(), "timezone": event.timezone},
        "event": {
            "name": event.name,
            "tagline": event.tagline,
            "starts_at": event.starts_at.isoformat(),
            "ends_at": event.ends_at.isoformat(),
        },
        "stage": {
            "width": display.stage_width,
            "height": display.stage_height,
            "safe": {
                "x": display.safe_x,
                "y": display.safe_y,
                "width": display.safe_width,
                "height": display.safe_height,
            },
            # The address changes with the artwork, so a screen that is already running
            # fetches a newly uploaded background instead of keeping the one it has.
            "background_url": (
                reverse("signage-api:background") + f"?v={display.background_version}"
            ),
        },
        # Every announcement that is on, the most important first. A screen shows the
        # first takeover alone, and otherwise the bars in turn.
        "announcements": announcements,
        "passes": passes,
        "warnings": warnings,
        "preview": bool(preview_slide),
    }


def stamp(bundle: dict[str, Any], now: datetime) -> dict[str, Any]:
    """A bundle with the time of this answer. Bundles are kept for a moment to be shared
    between screens, while each screen sets its clock by the time in the one it gets."""
    local = now.astimezone(ZoneInfo(bundle["clock"]["timezone"])).isoformat()
    return {**bundle, "generated_at": local, "clock": {**bundle["clock"], "now": local}}
