"""Shared plumbing for upstream systems. Every integration reads its connection settings
from the admin-managed Integration row, caches parsed results, and never raises into a
view: on failure it returns the last good value flagged stale, or an empty result."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache

from signage.models import Integration

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Result[T]:
    data: T | None
    stale: bool
    fetched_at: datetime | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.data is not None


def data_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


class IntegrationClient[T]:
    kind: str

    def __init__(self, config: Integration | None = None) -> None:
        self.config = config or Integration.objects.filter(kind=self.kind).first()

    @property
    def enabled(self) -> bool:
        return bool(self.config and self.config.is_configured)

    @property
    def cache_key(self) -> str:
        return f"signage:integration:{self.kind}"

    def fetch(self) -> Result[T]:
        if not self.enabled:
            return Result(None, False, None, "disabled")
        cached = cache.get(self.cache_key)
        if cached is not None:
            return Result(cached["data"], False, cached["fetched_at"])
        try:
            data = self._request()
        except Exception as error:
            log.warning("%s upstream failed: %s", self.kind, type(error).__name__)
            last = cache.get(f"{self.cache_key}:last")
            if last is not None:
                return Result(last["data"], True, last["fetched_at"], type(error).__name__)
            return Result(None, True, None, type(error).__name__)
        fetched_at = datetime.now(UTC)
        payload = {"data": data, "fetched_at": fetched_at}
        cache.set(self.cache_key, payload, self.config.cache_seconds)
        cache.set(f"{self.cache_key}:last", payload, settings.SIGNAGE_LAST_GOOD_SECONDS)
        return Result(data, False, fetched_at)

    def _request(self) -> T:
        raise NotImplementedError

    def client(self) -> httpx.Client:
        assert self.config is not None
        verify: bool | str = self.config.verify_tls
        if self.config.verify_tls and self.config.ca_bundle:
            verify = self.config.ca_bundle
        return httpx.Client(
            base_url=self.config.base_url,
            headers={"Accept": "application/json", **self.config.auth_headers()},
            auth=self.config.basic_auth(),
            verify=verify,
            timeout=httpx.Timeout(
                connect=self.config.connect_timeout,
                read=self.config.read_timeout,
                write=self.config.read_timeout,
                pool=self.config.connect_timeout,
            ),
            follow_redirects=True,
        )

    def get_json(self, path: str, **params: Any) -> Any:
        with self.client() as client:
            response = client.get(path, params=params or None)
            response.raise_for_status()
            return response.json()

    def status(self) -> dict[str, Any]:
        """For the admin overview: configuration and freshness in one dict."""
        cached = cache.get(self.cache_key)
        last = cache.get(f"{self.cache_key}:last")
        return {
            "kind": self.kind,
            "enabled": self.enabled,
            "base_url": self.config.base_url if self.config else "",
            "fresh": cached is not None,
            "last_fetch": (cached or last or {}).get("fetched_at"),
        }
