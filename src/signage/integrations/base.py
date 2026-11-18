"""Shared plumbing for upstream systems. Every integration reads its connection settings
from the admin-managed Integration row, caches parsed results, and never raises into a
view: on failure it returns the last good value flagged stale, or an empty result.

A failure is remembered for as long as a success would be, so an upstream that is down is
asked once per cache period and not once per screen, and never by two requests at once.

One fetch is one operation against the upstream, however many requests it takes: it has
MAX_UPSTREAM_SECONDS at most, less when the bundle that asks has less time left. Every
request gets what is left of that, answers are read in chunks against it, and no answer
may be larger than its format allows.
"""

from __future__ import annotations

import fcntl
import json
import logging
import ssl
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

import httpx
from django.conf import settings
from django.core.cache import cache

from signage.models import MAX_UPSTREAM_SECONDS, Integration

log = logging.getLogger(__name__)

# What an upstream that is down, slow or misconfigured answers with. Anything else is a
# defect in the parsing, which is logged with its traceback.
EXPECTED_ERRORS = (httpx.HTTPError, httpx.InvalidURL, ValueError, KeyError, TypeError, OSError)


class OperationTimeout(httpx.TimeoutException):
    """The operation used up its time, between requests or while an answer came in."""

    def __init__(self) -> None:
        super().__init__("The upstream did not answer in the time this request had for it.")


class AnswerTooLargeError(ValueError):
    pass


@dataclass(frozen=True)
class Budget:
    """The time an upstream operation has: until `deadline`, by `clock`."""

    deadline: float
    clock: Callable[[], float]

    def remaining(self) -> float:
        """The seconds left. When none are, the operation is over."""
        left = self.deadline - self.clock()
        if left <= 0:
            raise OperationTimeout
        return left


class Snapshot[T](TypedDict):
    """An answer as the cache keeps it: what the upstream said, and when it was fetched."""

    data: T
    fetched_at: datetime


@dataclass(frozen=True)
class Result[T]:
    data: T | None
    stale: bool
    fetched_at: datetime | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.data is not None


def describe(error: BaseException, base_url: str = "") -> str:
    """One line that tells an HTTP 403 from a timeout from a missing key."""
    if isinstance(error, httpx.HTTPStatusError) and error.response.is_redirect:
        return _redirect_hint(error, base_url)
    text = str(error).strip()
    return f"{type(error).__name__}: {text}" if text else type(error).__name__


def _redirect_hint(error: httpx.HTTPStatusError, base_url: str) -> str:
    """What to configure instead of an address that redirects, as the client doesn't follow
    redirects. The usual one keeps the path and changes the scheme or the host, as from
    plain HTTP to HTTPS; then the API root on the new address is named."""
    requested = error.request.url
    target = requested.join(error.response.headers.get("location", ""))
    endpoint = requested.path.removeprefix(httpx.URL(base_url).path.rstrip("/"))
    if base_url and endpoint and target.path.endswith(endpoint):
        root = target.copy_with(path=target.path.removesuffix(endpoint), query=None)
        return f"The server redirects to {target}: set the API root to {root}."
    return f"The server redirects to {target}, and redirects aren't followed: check the API root."


@contextmanager
def refresh_lock(key: str, *, wait: bool = False) -> Iterator[bool]:
    """One refresher across gunicorn processes and threads. Django's filesystem cache
    implements `add` as a separate read and write, so it cannot provide this lock. The
    file lock lasts through the request, even when an upstream takes longer than the
    cache period, and the OS releases it if a worker exits. With `wait`, it waits for the
    holder to finish instead of yielding False."""
    directory = Path(settings.SIGNAGE_LOCK_DIR)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / f"{key}.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            try:
                yield True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def media_type(response: httpx.Response) -> str:
    return response.headers.get("content-type", "").split(";")[0].strip().lower()


class IntegrationClient[T]:
    kind: str
    # Where the time of an operation comes from; tests replace it.
    clock: Callable[[], float] = staticmethod(time.monotonic)

    def __init__(self, config: Integration | None = None) -> None:
        self.config = config or Integration.objects.filter(kind=self.kind).first()

    @property
    def enabled(self) -> bool:
        return bool(self.config and self.config.is_configured)

    @property
    def cache_key(self) -> str:
        fingerprint = self.config.fingerprint if self.config else "none"
        return f"signage:integration:{self.kind}:{fingerprint}"

    # What an answer says about itself. Projectile and Bracket answer with what they have;
    # Streams can answer that it can't see its media server (see StreamsClient).

    def confirms(self, data: T) -> bool:
        """Whether the answer is an observation that may replace the last good one."""
        return True

    def reports_stale(self, data: T) -> bool:
        """Whether the upstream says that its own answer is out of date."""
        return False

    def observation_age(self, data: T, fetched_at: datetime, now: datetime) -> float | None:
        """How old what the answer describes is, in seconds, when the upstream says."""
        return None

    # How long an observation may stand in, by `observation_age`. None: any age.
    max_observation_age: float | None = None

    def unavailable(self, data: T) -> T:
        """What is shown when the upstream answered but can confirm nothing at all."""
        return data

    def budget(self, deadline: float | None = None) -> Budget:
        """The time of one operation: MAX_UPSTREAM_SECONDS, or what is left before `deadline`
        when that is less."""
        own = self.clock() + MAX_UPSTREAM_SECONDS
        return Budget(own if deadline is None else min(own, deadline), self.clock)

    def fetch(self, deadline: float | None = None) -> Result[T]:
        """The cached answer, or a fresh one. Past `deadline`, a value of `clock`, the upstream
        isn't asked: the last good answer stands in, so that one request never waits for
        every slow system in turn."""
        if not self.enabled:
            return Result(None, False, None, "disabled")
        cached = cache.get(self.cache_key)
        if cached is not None:
            return self._resolve(cached)

        failure = cache.get(f"{self.cache_key}:failed")
        if failure is not None:
            return self._last_good(failure)

        assert self.config is not None
        if deadline is not None and self.clock() >= deadline:
            return self._last_good("not asked: the bundle had no time left for it")
        seconds = self.config.cache_seconds
        with refresh_lock(f"{self.kind}-{self.config.fingerprint}") as acquired:
            if not acquired:
                return self._last_good("refreshing")
            # Another worker may have finished between the cache lookup and this lock.
            if cached := cache.get(self.cache_key):
                return self._resolve(cached)
            if failure := cache.get(f"{self.cache_key}:failed"):
                return self._last_good(failure)
            if not cache.add(f"{self.cache_key}:fetching", True, seconds):
                return self._last_good("refreshing")

            try:
                data = self._request(self.budget(deadline))
                payload: Snapshot[T] = {"data": data, "fetched_at": datetime.now(UTC)}
                cache.set(self.cache_key, payload, seconds)
                if self.confirms(data):
                    cache.set(f"{self.cache_key}:last", payload, settings.SIGNAGE_LAST_GOOD_SECONDS)
                return self._resolve(payload)
            except EXPECTED_ERRORS as error:
                problem = describe(error, self.config.base_url)
                log.warning("%s upstream failed: %s", self.kind, problem)
                return self._failed(problem, seconds)
            except Exception as error:
                log.exception("%s upstream answer could not be read", self.kind)
                return self._failed(describe(error), seconds)
            finally:
                cache.delete(f"{self.cache_key}:fetching")

    def _usable(self, payload: Snapshot[T]) -> bool:
        if self.max_observation_age is None:
            return True
        age = self.observation_age(payload["data"], payload["fetched_at"], datetime.now(UTC))
        return age is not None and age <= self.max_observation_age

    def _resolve(self, payload: Snapshot[T]) -> Result[T]:
        """What an answer amounts to: itself while it confirms something recent enough, and
        otherwise the last good answer, as for a failure."""
        data = payload["data"]
        if self.confirms(data) and self._usable(payload):
            return Result(data, self.reports_stale(data), payload["fetched_at"])
        return self._last_good(UNCONFIRMED, unconfirmed=data)

    def _failed(self, error: str, seconds: int) -> Result[T]:
        cache.set(f"{self.cache_key}:failed", error, seconds)
        return self._last_good(error)

    def _last_good(self, error: str, *, unconfirmed: T | None = None) -> Result[T]:
        last = cache.get(f"{self.cache_key}:last")
        if last is not None and self._usable(last):
            return Result(last["data"], True, last["fetched_at"], error)
        if unconfirmed is not None:
            return Result(self.unavailable(unconfirmed), True, None, error)
        return Result(None, True, None, error)

    def _request(self, budget: Budget) -> T:
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
            # The client carries the upstream's credentials, which a redirect would hand
            # to wherever it points.
            follow_redirects=False,
        )

    def receive(
        self,
        client: httpx.Client,
        url: str,
        budget: Budget,
        *,
        max_bytes: int,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        accept: tuple[str, Callable[[str], bool]] | None = None,
        follow: bool = False,
    ) -> tuple[httpx.Response, bytes]:
        """GET `url` within `budget`. With `follow`, a redirect is returned unread, for the
        caller to judge where it points; otherwise it fails like any other refusal. A
        success has to be of a media type that `accept` takes, a description and a test, and
        at most `max_bytes` long. It is read in chunks, so that neither a large answer nor one
        that trickles in keeps the request past its time."""
        assert self.config is not None
        left = budget.remaining()
        connect = min(self.config.connect_timeout, left)
        read = min(self.config.read_timeout, left)
        timeout = httpx.Timeout(connect=connect, read=read, write=read, pool=connect)
        with client.stream("GET", url, params=params, headers=headers, timeout=timeout) as answer:
            if follow and answer.is_redirect:
                return answer, b""
            answer.raise_for_status()
            if accept is not None and not accept[1](media_type(answer)):
                kind = media_type(answer) or "of an unknown type"
                raise ValueError(f"the answer is {kind}, not {accept[0]}")
            length = answer.headers.get("content-length", "")
            if length.isdigit() and int(length) > max_bytes:
                raise AnswerTooLargeError(f"the answer has {length} bytes, more than {max_bytes}")
            body = bytearray()
            for chunk in answer.iter_bytes():
                body += chunk
                if len(body) > max_bytes:
                    raise AnswerTooLargeError(f"the answer is longer than {max_bytes} bytes")
                budget.remaining()
            return answer, bytes(body)

    def get_json(self, path: str, budget: Budget, **params: Any) -> Any:
        with self.client() as client:
            _, body = self.receive(
                client,
                path,
                budget,
                max_bytes=settings.SIGNAGE_UPSTREAM_MAX_BYTES,
                params=params or None,
            )
        return json.loads(body)

    def status(self) -> dict[str, Any]:
        """For the admin overview: configuration and freshness in one dict."""
        cached = cache.get(self.cache_key)
        last = cache.get(f"{self.cache_key}:last")
        confirmed = cached is not None and self.confirms(cached["data"])
        error = cache.get(f"{self.cache_key}:failed")
        if cached is not None and not confirmed:
            error = UNCONFIRMED
        return {
            "kind": self.kind,
            "enabled": self.enabled,
            "base_url": self.config.base_url if self.config else "",
            "fresh": confirmed,
            "last_fetch": (cached or last or {}).get("fetched_at"),
            "error": None if confirmed else error,
        }


# Shown in the admin when an upstream answered but could not vouch for its data.
UNCONFIRMED = "answered, but cannot confirm its data right now"
