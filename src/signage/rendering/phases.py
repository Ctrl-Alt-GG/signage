from __future__ import annotations

from datetime import datetime

from signage.models import Event, Phase


def resolve_phase(event: Event, now: datetime) -> Phase | None:
    """Return the phase in force at `now`. Manual mode trusts the admin; auto mode picks
    the phase that started last, by the phases' start times. `order` only breaks ties: it
    is how the admin lists them, and an organizer may move a start time without it."""
    phases = list(Phase.objects.order_by("order"))
    if not phases:
        return None
    if event.phase_mode == Event.PhaseMode.MANUAL:
        return event.current_phase or phases[0]
    by_start = sorted(phases, key=lambda phase: (phase.boundary(event), phase.order))
    if now >= event.ends_at:
        return by_start[-1]
    started = [phase for phase in by_start if phase.boundary(event) <= now]
    return started[-1] if started else by_start[0]
