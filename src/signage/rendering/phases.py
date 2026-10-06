from __future__ import annotations

from datetime import datetime

from signage.models import Event, Phase


def resolve_phase(event: Event, now: datetime) -> Phase | None:
    """Return the phase in force at `now`. Manual mode trusts the admin; auto mode
    picks the phase with the latest boundary at or before `now`."""
    phases = list(Phase.objects.order_by("order"))
    if not phases:
        return None
    if event.phase_mode == Event.PhaseMode.MANUAL:
        return event.current_phase or phases[0]
    if now >= event.ends_at:
        return phases[-1]
    current = phases[0]
    for phase in phases:
        if phase.boundary(event) <= now:
            current = phase
    return current
