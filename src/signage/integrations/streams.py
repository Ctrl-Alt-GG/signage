"""Streams: the MediaMTX catalog. `GET {base_url}/streams/` lists channels with a
status; only live ones go on the wall."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from signage.integrations.base import IntegrationClient
from signage.models import Integration

MAX_REDIRECTS = 3


def parse_streams(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("source") or {}
    live = []
    for raw in payload.get("results") or []:
        if raw.get("status") != "live":
            continue
        live.append(
            {
                "id": str(raw.get("id")),
                "name": raw.get("effective_name") or raw.get("display_name") or "?",
                "audio_only": bool(raw.get("audio_only")),
                "thumbnail_url": raw.get("thumbnail_url") or "",
                "watch_url": raw.get("watch_url") or "",
            }
        )
    return {"live": live, "source_status": source.get("status", "unknown")}


class StreamsClient(IntegrationClient[dict[str, Any]]):
    kind = Integration.Kind.STREAMS

    def _request(self) -> dict[str, Any]:
        return parse_streams(self.get_json("/streams/"))

    def thumbnail_source(self, stream_id: str) -> str | None:
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

    def fetch_bytes(self, url: str) -> tuple[bytes, str]:
        """Fetch a thumbnail, following redirects only as far as they stay with Streams."""
        target = self.thumbnail_target(url)
        with self.client() as client:
            for _ in range(MAX_REDIRECTS + 1):
                response = client.get(target, headers={"Accept": "image/*"})
                if not response.is_redirect:
                    break
                target = self.thumbnail_target(response.headers.get("location", ""))
            response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        # The answer is passed on from this origin, so it has to be a picture.
        if not content_type.startswith("image/"):
            raise ValueError(f"thumbnail is {content_type or 'of an unknown type'}, not a picture")
        return response.content, content_type
