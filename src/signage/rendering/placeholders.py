from __future__ import annotations

import re

from signage.content.lint import PLACEHOLDER_RE

UNRESOLVED_MARKER = "CHANGE-ME"


class UnresolvedPlaceholderError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


def resolve(text: str, values: dict[str, str]) -> str:
    """Fill `{placeholders}` from `values`, which is `Event.placeholder_values` for one
    language. Raises when a value is unknown, missing or still a CHANGE-ME marker, so the
    caller can drop the slide instead of showing a gap.

    Only the names are looked at. A brace that is not part of a placeholder is ordinary
    text, and so is a brace inside a value: a Wi-Fi password may contain one.
    """
    if not text:
        return text
    if UNRESOLVED_MARKER in text:
        raise UnresolvedPlaceholderError(UNRESOLVED_MARKER)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = values.get(name)
        if value is None or not value.strip() or UNRESOLVED_MARKER in value:
            raise UnresolvedPlaceholderError(name)
        return value

    return PLACEHOLDER_RE.sub(replace, text)
