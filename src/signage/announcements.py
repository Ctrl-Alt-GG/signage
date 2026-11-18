"""Announcements made from a template. The organizer fills in what the template asks for and
the event does not know; the preview and the published announcement are made the same way,
and publishing puts the announcement on its screens in one step."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction

from signage.content.lint import PLACEHOLDER_RE
from signage.models import LANGS, Announcement, AnnouncementTemplate, Event, Screen


def _usable(value: str | None, unresolved_marker: str) -> bool:
    return bool(value and value.strip() and unresolved_marker not in value)


@dataclass(frozen=True)
class Filling:
    """How a template's placeholders get their values: those the event knows in both
    languages (`from_event`), and the rest, which the organizer types (`asked`)."""

    template: AnnouncementTemplate
    known: dict[str, dict[str, str]]
    from_event: list[str]
    asked: list[str]

    @classmethod
    def of(cls, template: AnnouncementTemplate, event: Event) -> Filling:
        from signage.rendering.placeholders import UNRESOLVED_MARKER

        known = {lang: event.placeholder_values(lang) for lang in LANGS}
        from_event = [
            name
            for name in template.placeholders
            if all(_usable(known[lang].get(name), UNRESOLVED_MARKER) for lang in LANGS)
        ]
        asked = [name for name in template.placeholders if name not in from_event]
        return cls(template, known, from_event, asked)

    def compose(self, typed: dict[str, str], now: datetime, minutes: int, user) -> Announcement:
        """The announcement, not saved: the template's text in both languages with the
        values filled in, from `now` for `minutes` (0: until ended in the list). Raises
        ValidationError when that is not a valid announcement."""
        template = self.template
        announcement = Announcement(
            level=template.level,
            takeover=template.takeover,
            starts_at=now,
            ends_at=now + timedelta(minutes=minutes) if minutes else None,
            template=template,
            created_by=user,
        )
        for lang in LANGS:
            values = {**{name: self.known[lang][name] for name in self.from_event}, **typed}
            text = PLACEHOLDER_RE.sub(
                lambda match, values=values: values.get(match.group(1), match.group(0)),
                template.text("text", lang),
            )
            setattr(announcement, f"text_{lang}", text)
        announcement.full_clean()
        return announcement


def publish(announcement: Announcement, screens: list[Screen]) -> Announcement:
    """Saves the announcement for `screens`, every screen when none. The announcement and its
    screens are saved in one transaction: no screen ever shows it without the screens it is
    meant for, and a failure leaves no announcement at all."""
    with transaction.atomic():
        announcement.save()
        announcement.screens.set(screens)
    return announcement
