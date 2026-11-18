"""Rows that two writers can change at the same time: organizers in the admin, and the YAML
import that runs on every start. Both read a row with a lock before they decide on it, so
neither writes over a change it has not seen; an admin page also refuses a change made over
one that was saved after the page was opened (see `admin.ConcurrentEditMixin`)."""

from __future__ import annotations

import hashlib

from django.db import models


def row_version(row: models.Model) -> str:
    """Identifies what a row holds, as stored: its fields and many-to-many relations. Any
    change to them, by anyone, gives another version."""
    meta = row._meta
    parts = [f"{field.attname}={field.value_to_string(row)}" for field in meta.concrete_fields]
    for field in meta.many_to_many:
        keys = sorted(str(key) for key in getattr(row, field.name).values_list("pk", flat=True))
        parts.append(f"{field.name}={','.join(keys)}")
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


def locked[M: models.Model](queryset: models.QuerySet[M]) -> M | None:
    """The row of `queryset` as stored now, locked until the transaction ends: a writer that
    got there first has finished, and a later one waits."""
    return queryset.select_for_update().first()
