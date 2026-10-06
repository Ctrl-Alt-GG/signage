from __future__ import annotations

import re

from signage.models import PLACEHOLDER_RE, Event

UNRESOLVED_MARKER = "CHANGE-ME"
_BRACES = re.compile(r"[{}]")


class UnresolvedPlaceholderError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


def resolve(text: str, event: Event, lang: str) -> str:
    """Fill `{placeholders}` from the event. Raises when a value is missing or still a
    CHANGE-ME marker, so the caller can drop the slide instead of showing a gap."""
    if not text:
        return text
    values = event.placeholder_values(lang)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = values.get(name)
        if value is None or not value.strip() or UNRESOLVED_MARKER in value:
            raise UnresolvedPlaceholderError(name)
        return value

    resolved = PLACEHOLDER_RE.sub(replace, text)
    if _BRACES.search(resolved):
        raise UnresolvedPlaceholderError(resolved)
    if UNRESOLVED_MARKER in resolved:
        raise UnresolvedPlaceholderError(UNRESOLVED_MARKER)
    return resolved
