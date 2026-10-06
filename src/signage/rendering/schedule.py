"""Now / next / later view of the schedule, plus the upcoming window."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from signage.models import Event, ScheduleEntry


@dataclass(frozen=True)
class EntryView:
    time: str
    type: str
    label: str
    title: dict[str, str]
    note: dict[str, str]
    game: dict[str, str] | None
    starts_at: str


@dataclass
class ScheduleView:
    now: list[EntryView] = field(default_factory=list)
    next: list[EntryView] = field(default_factory=list)
    later: list[EntryView] = field(default_factory=list)
    upcoming: list[EntryView] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _entry_view(entry: ScheduleEntry, starts_at: datetime) -> EntryView:
    game = None
    if entry.game:
        game = {
            "slug": entry.game.slug,
            "name": entry.game.name,
            "short": entry.game.short,
            "color_bg": entry.game.color_bg,
            "color_text": entry.game.color_text,
        }
    return EntryView(
        time=starts_at.strftime("%H:%M"),
        type=entry.type,
        label=entry.label,
        title=entry.pair("title"),
        note=entry.pair("note"),
        game=game,
        starts_at=starts_at.isoformat(),
    )


def build_schedule_view(event: Event, now: datetime, upcoming_count: int = 8) -> ScheduleView:
    entries = list(ScheduleEntry.objects.select_related("game"))
    timed = sorted(((entry.starts_at(event), entry) for entry in entries), key=lambda pair: pair[0])
    # Entries that share a start time form one group.
    groups: list[tuple[datetime, list[ScheduleEntry]]] = []
    for starts_at, entry in timed:
        if groups and groups[-1][0] == starts_at:
            groups[-1][1].append(entry)
        else:
            groups.append((starts_at, [entry]))

    view = ScheduleView()
    if not groups or now >= event.ends_at:
        return view

    current_index = -1
    for index, (starts_at, _) in enumerate(groups):
        if starts_at <= now:
            current_index = index

    def views(index: int) -> list[EntryView]:
        if 0 <= index < len(groups):
            starts_at, members = groups[index]
            return [_entry_view(entry, starts_at) for entry in members]
        return []

    view.now = views(current_index)
    view.next = views(current_index + 1)
    view.later = views(current_index + 2)
    start = max(current_index, 0)
    for index in range(start, len(groups)):
        view.upcoming.extend(views(index))
        if len(view.upcoming) >= upcoming_count:
            break
    view.upcoming = view.upcoming[:upcoming_count]
    return view
