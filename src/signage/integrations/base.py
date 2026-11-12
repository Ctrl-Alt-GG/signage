"""Shared plumbing for upstream systems. Every integration reads its connection settings
from the admin-managed Integration row, caches parsed results, and never raises into a
view: on failure it returns the last good value flagged stale, or an empty result.

A failure is remembered for as long as a success would be, so an upstream that is down is
asked once per cache period and not once per screen, and never by two requests at once.
"""

from __future__ import annotations

import fcntl
import logging
import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache

from signage.models import Integration

log = logging.getLogger(__name__)

# What an upstream that is down, slow or misconfigured answers with. Anything else is a
# defect in the parsing, which is logged with its traceback.
EXPECTED_ERRORS = (httpx.HTTPError, httpx.InvalidURL, ValueError, KeyError, TypeError, OSError)


@dataclass(frozen=True)
class Result[T]:
    data: T | None
    stale: bool
    fetched_at: datetime | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.data is not None


def describe(error: BaseException) -> str:
    """One line that tells an HTTP 403 from a timeout from a missing key."""
    text = str(error).strip()
    return f"{type(error).__name__}: {text}" if text else type(error).__name__


@contextmanager
def refresh_lock(key: str) -> Iterator[bool]:
    """One refresher across gunicorn processes and threads. Django's filesystem cache
    implements `add` as a separate read and write, so it cannot provide this lock. The
    file lock lasts through the request, even when an upstream takes longer than the
    cache period, and the OS releases it if a worker exits."""
    directory = Path(settings.SIGNAGE_LOCK_DIR)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / f"{key}.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            try:
                yield True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


class IntegrationClient[T]:
    kind: str

    def __init__(self, config: Integration | None = None) -> None:
        self.config = config or Integration.objects.filter(kind=self.kind).first()

    @property
    def enabled(self) -> bool:
        return bool(self.config and self.config.is_configured)

    @property
    def cache_key(self) -> str:
        fingerprint = self.config.fingerprint if self.config else "none"
        return f"signage:integration:{self.kind}:{fingerprint}"

    def fetch(self) -> Result[T]:
        if not self.enabled:
            return Result(None, False, None, "disabled")
        cached = cache.get(self.cache_key)
        if cached is not None:
            return Result(cached["data"], False, cached["fetched_at"])

        failure = cache.get(f"{self.cache_key}:failed")
        if failure is not None:
            return self._last_good(failure)

        assert self.config is not None
        seconds = self.config.cache_seconds
        with refresh_lock(f"{self.kind}-{self.config.fingerprint}") as acquired:
            if not acquired:
                return self._last_good("refreshing")
            # Another worker may have finished between the cache lookup and this lock.
            if cached := cache.get(self.cache_key):
                return Result(cached["data"], False, cached["fetched_at"])
            if failure := cache.get(f"{self.cache_key}:failed"):
                return self._last_good(failure)
            if not cache.add(f"{self.cache_key}:fetching", True, seconds):
                return self._last_good("refreshing")

            try:
                data = self._request()
                fetched_at = datetime.now(UTC)
                payload = {"data": data, "fetched_at": fetched_at}
                cache.set(self.cache_key, payload, seconds)
                cache.set(f"{self.cache_key}:last", payload, settings.SIGNAGE_LAST_GOOD_SECONDS)
                return Result(data, False, fetched_at)
            except EXPECTED_ERRORS as error:
                log.warning("%s upstream failed: %s", self.kind, describe(error))
                return self._failed(describe(error), seconds)
            except Exception as error:
                log.exception("%s upstream answer could not be read", self.kind)
                return self._failed(describe(error), seconds)
            finally:
                cache.delete(f"{self.cache_key}:fetching")

    def _failed(self, error: str, seconds: int) -> Result[T]:
        cache.set(f"{self.cache_key}:failed", error, seconds)
        return self._last_good(error)

    def _last_good(self, error: str) -> Result[T]:
        last = cache.get(f"{self.cache_key}:last")
        if last is not None:
            return Result(last["data"], True, last["fetched_at"], error)
        return Result(None, True, None, error)

    def _request(self) -> T:
        raise NotImplementedError

    def client(self) -> httpx.Client:
        assert self.config is not None
        verify: bool | ssl.SSLContext = self.config.verify_tls
        if self.config.verify_tls and self.config.ca_bundle:
            verify = ssl.create_default_context(cafile=self.config.ca_bundle)
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
            # The client carries the upstream's credentials, which a redirect would hand
            # to wherever it points.
            follow_redirects=False,
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
            "error": None if cached is not None else cache.get(f"{self.cache_key}:failed"),
        }
