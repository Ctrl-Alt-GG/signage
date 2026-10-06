"""Projectile: the game server list. `GET {base_url}/bundle` returns the announcement
and the servers with player counts."""

from __future__ import annotations

from typing import Any

from signage.integrations.base import IntegrationClient
from signage.models import Game, Integration

FALLBACK_COLOR = ("#777777", "#000000")


def _sort_key(server: dict[str, Any]) -> int:
    addresses = server.get("addresses") or []
    try:
        host = str(addresses[0]).split(":")[0]
        return int(host.split(".")[-1])
    except (IndexError, ValueError):
        return 10_000


def players_text(server: dict[str, Any]) -> str:
    capabilities = server.get("capabilities") or {}
    max_players = server.get("max_players")
    if capabilities.get("player_count") and max_players is not None:
        return f"{server.get('online_players', 0)} / {max_players}"
    return f"max: {max_players}" if max_players is not None else ""


def parse_bundle(payload: dict[str, Any], games: list[Game]) -> dict[str, Any]:
    by_key: dict[str, Game] = {}
    for game in games:
        for key in game.projectile_keys:
            by_key[key.lower()] = game
    servers = []
    for raw in sorted(payload.get("gameServers") or [], key=_sort_key):
        key = str(raw.get("game") or "").lower()
        game = by_key.get(key)
        servers.append(
            {
                "name": raw.get("name") or key or "?",
                "info": raw.get("info") or "",
                "game_slug": game.slug if game else key,
                "game_name": game.name if game else (key or "?"),
                "game_short": game.short if game else (key or "?"),
                "color_bg": game.color_bg if game else FALLBACK_COLOR[0],
                "color_text": game.color_text if game else FALLBACK_COLOR[1],
                "players_text": players_text(raw),
                "online_players": raw.get("online_players"),
                "max_players": raw.get("max_players"),
            }
        )
    announcement = (payload.get("announcement") or {}).get("text") or ""
    return {"servers": servers, "announcement": announcement.strip()}


class ProjectileClient(IntegrationClient[dict[str, Any]]):
    kind = Integration.Kind.PROJECTILE

    def _request(self) -> dict[str, Any]:
        payload = self.get_json("/bundle")
        return parse_bundle(payload, list(Game.objects.all()))
