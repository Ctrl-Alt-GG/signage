"""Streams: the MediaMTX catalog. `GET {base_url}/streams/` lists channels with a
status; only live ones go on the wall."""

from __future__ import annotations

from typing import Any

from signage.integrations.base import IntegrationClient
from signage.models import Integration


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

    def fetch_bytes(self, url: str) -> tuple[bytes, str]:
        with self.client() as client:
            response = client.get(url, headers={"Accept": "image/*"})
            response.raise_for_status()
            return response.content, response.headers.get("content-type", "image/jpeg")
