"""Streams: the MediaMTX catalog. `GET {base_url}/streams/` lists channels with a
status; only live ones go on the wall.

Streams tells its channels apart from its own view of them: `source.status` says whether it
could check its media server recently (`fresh`), only a while ago (`stale`), or not at all
(`unavailable`), and `source.age_seconds` how old that check is. An answer it can't vouch for
is no observation: the channels last confirmed stay on the screen, marked as not current,
until they are SIGNAGE_STREAMS_RETAIN_SECONDS old by Streams' own count. A confirmed answer
replaces them at once, also when it has no live channel.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, NotRequired, TypedDict
from urllib.parse import urlsplit

from django.conf import settings

from signage.integrations.base import Budget, IntegrationClient, media_type
from signage.models import Integration

MAX_REDIRECTS = 3
SOURCE_STATES = ("fresh", "stale", "unavailable")


class Channel(TypedDict):
    id: str
    name: str
    audio_only: bool
    thumbnail_url: str
    watch_url: str


class StreamsData(TypedDict):
    live: list[Channel]
    # fresh, stale or unavailable. Anything else Streams might say counts as unavailable.
    source_status: str
    observed_at: str | None
    age_seconds: NotRequired[float | None]


def _age(source: dict[str, Any]) -> float | None:
    value = source.get("age_seconds")
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        return None
    return float(value)


def parse_streams(payload: dict[str, Any]) -> StreamsData:
    source = payload.get("source") or {}
    status = source.get("status")
    live: list[Channel] = []
    for raw in payload.get("results") or []:
        # A channel whose status can't be confirmed is not shown as live.
        if not isinstance(raw, dict) or raw.get("status") != "live":
            continue
        live.append(
            {
                "id": str(raw.get("id")),
                "name": str(raw.get("effective_name") or raw.get("display_name") or "?"),
                "audio_only": bool(raw.get("audio_only")),
                "thumbnail_url": str(raw.get("thumbnail_url") or ""),
                "watch_url": str(raw.get("watch_url") or ""),
            }
        )
    observed_at = source.get("observed_at")
    return {
        "live": live,
        "source_status": status if status in SOURCE_STATES else "unavailable",
        "observed_at": observed_at if isinstance(observed_at, str) else None,
        "age_seconds": _age(source),
    }


class StreamsClient(IntegrationClient[StreamsData]):
    kind = Integration.Kind.STREAMS

    @property
    def max_observation_age(self) -> float:
        return settings.SIGNAGE_STREAMS_RETAIN_SECONDS

    def confirms(self, data: StreamsData) -> bool:
        return data["source_status"] in ("fresh", "stale")

    def reports_stale(self, data: StreamsData) -> bool:
        return data["source_status"] != "fresh"

    def observation_age(
        self, data: StreamsData, fetched_at: datetime, now: datetime
    ) -> float | None:
        # By Streams' count when it answered, then by this server's clock: the two clocks
        # needn't agree, and a cached answer keeps ageing.
        age = data.get("age_seconds")
        if age is None:
            return None if data["source_status"] != "fresh" else 0.0
        return age + max(0.0, (now - fetched_at).total_seconds())

    def unavailable(self, data: StreamsData) -> StreamsData:
        return {**data, "live": [], "source_status": "unavailable"}

    def _request(self, budget: Budget) -> StreamsData:
        return parse_streams(self.get_json("/streams/", budget))

    def thumbnail_source(self, stream_id: str) -> str | None:
        # The same channels as on the screen: retained ones keep their pictures.
        result = self.fetch()
        for channel in (result.data or {}).get("live", []):
            if channel["id"] == stream_id:
                return channel["thumbnail_url"] or None
        return None

    def thumbnail_target(self, url: str) -> str:
        """Where a thumbnail is fetched from: its path, on the address Streams was configured
        with. Streams names its public address in the URLs it hands out, which need not be
        the one this server reaches it by. Only the path is taken from the answer, so the
        credentials this client carries never go anywhere else."""
        assert self.config is not None
        base, wanted = urlsplit(self.config.base_url), urlsplit(url)
        if wanted.scheme not in ("", "http", "https") or not wanted.path.startswith("/"):
            raise ValueError(f"not a thumbnail address: {url}")
        query = f"?{wanted.query}" if wanted.query else ""
        return f"{base.scheme}://{base.netloc}{wanted.path}{query}"

    def fetch_bytes(self, url: str, budget: Budget | None = None) -> tuple[bytes, str]:
        """Fetch a thumbnail, following redirects only as far as they stay with Streams. All
        the requests share one operation's time."""
        budget = budget or self.budget()
        target = self.thumbnail_target(url)
        with self.client() as client:
            for _ in range(MAX_REDIRECTS + 1):
                answer, body = self.receive(
                    client,
                    target,
                    budget,
                    max_bytes=settings.SIGNAGE_THUMBNAIL_MAX_BYTES,
                    headers={"Accept": "image/*"},
                    # The answer is passed on from this origin, so it has to be a picture.
                    accept=("a picture", lambda kind: kind.startswith("image/")),
                    follow=True,
                )
                if not answer.is_redirect:
                    return body, media_type(answer)
                target = self.thumbnail_target(answer.headers.get("location", ""))
        raise ValueError(f"the thumbnail redirects more than {MAX_REDIRECTS} times")
