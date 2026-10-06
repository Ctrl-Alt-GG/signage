"""Build the JSON bundle a screen polls: the slides in rotation, expanded into language
passes, plus the active announcement, the phase and the clock. See docs/spec.md section 6."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

from django.conf import settings
from django.urls import reverse

from signage.integrations.bracket import BracketClient
from signage.integrations.projectile import ProjectileClient
from signage.integrations.streams import StreamsClient
from signage.models import LANGS, Announcement, Event, Integration, Phase, Screen, Slide
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


def _resolved_pair(slide: Slide, field: str, event: Event) -> dict[str, str]:
    return {lang: resolve(slide.text(field, lang), event, lang) for lang in LANGS}


def _resolved_items(items, event: Event) -> list[dict[str, str]]:
    return [
        {
            "hu": resolve(item.text_hu, event, "hu"),
            "en": resolve(item.text_en, event, "en"),
            "icon": item.icon,
        }
        for item in items
    ]


def slide_content(slide: Slide, event: Event) -> dict[str, Any]:
    items = list(slide.items.all())
    content: dict[str, Any] = {
        "kicker": _resolved_pair(slide, "kicker", event),
        "title": _resolved_pair(slide, "title", event),
        "body": _resolved_pair(slide, "body", event),
        "footer": _resolved_pair(slide, "footer", event),
        "empty": _resolved_pair(slide, "empty", event),
        "items": _resolved_items([i for i in items if i.column == 1], event),
        "columns": [],
        "labels": slide.labels or {},
        "link": None,
    }
    if slide.layout == Slide.Layout.SPLIT:
        content["columns"] = [
            {
                "title": _resolved_pair(slide, f"column{column}_title", event),
                "items": _resolved_items([i for i in items if i.column == column], event),
            }
            for column in (1, 2)
        ]
        content["items"] = []
    if slide.link_url or slide.link_qr:
        url = slide.link_url
        qr_payload = _wifi_payload(event) if url == "wifi" else url
        content["link"] = {
            "url": "" if url == "wifi" else url,
            "label": _resolved_pair(slide, "link_label", event),
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
    data["stale"] = result.stale
    if slide.source == Slide.Source.STREAMS:
        for channel in data.get("live", []):
            channel["thumbnail_url"] = reverse(
                "signage-api:thumbnail", kwargs={"stream_id": channel["id"]}
            )
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


def active_announcement(screen: Screen, now: datetime) -> Announcement | None:
    rank = {"urgent": 0, "warning": 1, "info": 2}
    candidates = [
        a
        for a in Announcement.objects.filter(enabled=True, starts_at__lte=now).prefetch_related(
            "screens"
        )
        if a.is_active(now) and (not a.screens.exists() or a.screens.filter(pk=screen.pk).exists())
    ]
    candidates.sort(key=lambda a: (rank[a.level], -a.created_at.timestamp()))
    return candidates[0] if candidates else None


def _mirrored_announcement(now: datetime) -> dict | None:
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


def _passes_for(slide: Slide, screen: Screen, content: dict, live: dict | None) -> list[dict]:
    duration_ms = slide.duration_seconds * 1000
    base = {
        "slide": slide.key,
        "layout": slide.layout,
        "source": slide.source,
        "duration_ms": duration_ms,
        "content": content,
        "live": live,
    }
    if screen.language_mode in LANGS:
        return [
            {**base, "key": f"{slide.key}:{screen.language_mode}", "lang": screen.language_mode}
        ]
    if slide.bilingual_mode == Slide.BilingualMode.STACKED:
        return [{**base, "key": f"{slide.key}:both", "lang": "both"}]
    return [{**base, "key": f"{slide.key}:{lang}", "lang": lang} for lang in LANGS]


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

    passes: list[dict] = []
    hash_parts: list[str] = [phase.key if phase else "-", screen.slug, str(screen.updated_at)]
    for slide in slides:
        live = live_data(slide, event, now, warnings)
        if slide.is_live and live is None and not preview_slide:
            continue
        try:
            content = slide_content(slide, event)
        except UnresolvedPlaceholderError as error:
            warnings.append(f"{slide.key}: unresolved placeholder {error.name}")
            if not preview_slide:
                continue
            content = {"title": slide.pair("title"), "items": [], "columns": [], "labels": {}}
        slide_passes = _passes_for(slide, screen, content, live)
        if preview_slide and preview_lang in (*LANGS, "both"):
            slide_passes = [
                {**slide_passes[0], "key": f"{slide.key}:{preview_lang}", "lang": preview_lang}
            ]
        passes.extend(slide_passes)
        hash_parts.append(f"{slide.key}:{slide.updated_at.isoformat()}")
        if live is not None:
            hash_parts.append(hashlib.sha256(repr(sorted(live.items())).encode()).hexdigest()[:12])

    announcement_obj = None if preview_slide else active_announcement(screen, now)
    announcement: dict | None = None
    if announcement_obj:
        announcement = {
            "id": announcement_obj.pk,
            "level": announcement_obj.level,
            "takeover": announcement_obj.takeover,
            "text": announcement_obj.pair("text"),
            "ends_at": announcement_obj.ends_at.isoformat() if announcement_obj.ends_at else None,
        }
        hash_parts.append(f"ann:{announcement_obj.pk}:{announcement_obj.updated_at.isoformat()}")
    elif not preview_slide:
        announcement = _mirrored_announcement(now)
        if announcement:
            hash_parts.append("ann:projectile:" + announcement["text"]["hu"])

    version = hashlib.sha256("|".join(hash_parts).encode()).hexdigest()[:16]
    return {
        "version": version,
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
        "announcement": announcement,
        "passes": passes,
        "warnings": warnings,
        "preview": bool(preview_slide),
        "default_screen": settings.SIGNAGE_DEFAULT_SCREEN,
    }
