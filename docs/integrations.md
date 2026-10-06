# Integrations: the Ctrl-Alt-GG family

The signage is the eighth property in a family of small, opinionated
projects. This document records what each sibling is, what the signage takes
from it, and the exact contract where the signage talks to it at runtime.
Everything here was read from the public repositories on 2026-10-06; where a
fact could not be verified (for example a hostname that only resolves on the
venue network) it is marked "verify on site".

| System | Repository | URL | Stack | Signage uses it for | How |
|---|---|---|---|---|---|
| Homepage | `Ctrl-Alt-GG/homepage` | https://www.ctrl-alt-gg.hu | Hugo, Tailwind 4, Azure SWA, GHCR image | Schedule, programme, venue, social links, brand tokens, prose rules | Copied into `content/*.yaml` at authoring time |
| Care | `Ctrl-Alt-GG/care` | https://care.ctrl-alt-gg.hu | Hugo, Tailwind 4 | Help, rules, safety, food, network etiquette copy; QR target | Copied into `content/slides.yaml`; linked by QR |
| Spawn | `Ctrl-Alt-GG/link-collection` | https://spawn.ctrl-alt-gg.hu | Hugo, Tailwind 4, GHCR image | The list of on-site services, the Wi-Fi password | Copied into `content/event.yaml`; linked by QR |
| Projectile | `Ctrl-Alt-GG/projectile-frontend` (backend not public) | https://servers.ctrl-alt-gg.hu (verify on site) | Vue 3 frontend, JSON API | Live game server list with player counts | Runtime, `GET /api/bundle` |
| Bracket | `Ctrl-Alt-GG/brackets` (fork of evroon/bracket) | https://bracket.ctrl-alt-gg.hu | FastAPI backend, React 19 frontend, Postgres | Live tournament matches and results | Runtime, public dashboard endpoints |
| Streams | `Ctrl-Alt-GG/streams` | https://streams.ctrl-alt-gg.hu (network-private) | Django 6, DRF, Celery, MediaMTX | Which channels are live; the Django conventions this repo copies | Runtime, `GET /api/v1/streams/` |
| Network services | `Ctrl-Alt-GG/network-services` | internal | Ansible for Rocky Linux: Unbound, Kea, chrony, Docker hosts, nginx | Where the signage host and the kiosks live; DNS; TLS | Deployment context only |

## 1. Homepage

Bilingual marketing site, Hungarian default. The parts the signage copies:

- `content/schedule/_index.md` and `_index.en.md`: the 17-row timeline, now
  in `content/schedule.yaml`. The page itself says the next programme item
  "will be announced here and on the digital signage screens", so the
  `now_next` slide is the promised feature.
- `content/program/`: game list; hosted games carry an asterisk. Now in
  `content/games.yaml` as `hosted: true`.
- `content/location/`: venue, entrance, parking, transit stops and distances.
- `content/stuff/`: bring list, two outlets per person, the seven house rules.
- `content/qa/`: no catering, no sleeping at the venue.
- `content/aboutus/`: the four organizers and the contact address.
- `hugo.yaml` `params.cag.social_channels`: YouTube, Twitch and Steam are
  enabled; Discord, Kick, Facebook and X are off. The Discord invite comes
  from Spawn instead.
- `data/games.yaml`: slugs and header art URLs. The signage reuses the slugs
  and does not hot-link the art; game cards are colour blocks, see
  `docs/design.md`.
- `assets/css/main.css` `@theme`: the brand palette mirrored in
  `docs/design.md`.
- `.github/instructions/prose-style.instructions.md`: the prose rules
  this repo adopts verbatim (section 8 below).

The homepage countdown pointed at 2026-10-03 when read. Confirm the real
date with the organizers before seeding `event.starts_at`.

## 2. Care

Support hub "so nobody has to DM an organiser at 2 AM". Six sections:
network, hardware, software, wellness, logistics, help. The signage
condenses the following guides into slides: `help/how-to-get-help`,
`help/communication-channels`, `wellness/house-rules`,
`wellness/emergency-contacts`, `wellness/food-and-drink`,
`wellness/surviving-the-weekend`, `software/voice-chat-setup`,
`software/local-downloads`, `software/file-sharing`,
`software/watch-stream`, `software/publish-stream`,
`software/follow-tournament`, `logistics/during-the-tournament`,
`logistics/tournaments`, `network/cant-see-the-server`,
`network/bandwidth-etiquette`.

Some Care copy is generic across events (sleeping areas, showers, a
two-day format). The homepage FAQ for the DISTR3CT event says there is no
sleeping at the venue, so the signage follows the homepage where the two
disagree.

`help/known-issues` is a hand-edited status page. The signage does not
scrape it; organizers publish the same information as `known_issue`
announcements from the admin.

## 3. Spawn (link-collection)

The landing page that opens on the intranet wall. Single language. Its
`config.toml` `params.author.links` is the canonical list of on-site services
and is what the `spawn` slide lists:

```
homepage  https://home.ctrl-alt-gg.hu      (the public site is www.ctrl-alt-gg.hu)
care      https://care.ctrl-alt-gg.hu
lobby     https://lobby.ctrl-alt-gg.hu
bracket   https://bracket.ctrl-alt-gg.hu
streams   https://streams.ctrl-alt-gg.hu
filehost  https://filehost.ctrl-alt-gg.hu
servers   https://servers.ctrl-alt-gg.hu
discord   https://discord.gg/TVJ5Xh2NC3
steam     https://steamcommunity.com/groups/Ctrl-Alt-GG
# commented out, future: files.ctrl-alt-gg.hu, speed.ctrl-alt-gg.hu, a Google Calendar
```

`content/_index.md` carries the Wi-Fi password in plain text, which is why
the `wifi` slide may show it too. The SSID is not published anywhere.

Spawn is also published as a GHCR image "so it can run on the intranet if
Azure is unreachable". The signage follows the same principle: no runtime
dependency on anything outside the venue network.

## 4. Projectile (game server list)

Vue 3 single-page app with three routes: `/` (desktop list), `/wall`
(projector view, polls every 5 seconds, black background) and `/admin`
(password-protected). The backend is not in a public repository; the frontend
calls it at the relative path `/api`, so the base URL is the server-list host
plus `/api` (verify on site).

### Read endpoint the signage uses

`GET {PROJECTILE_API_BASE_URL}/bundle`

Response shape, reconstructed from `WallView.vue`, `GameserverCard.vue` and
`AdminView.vue`:

```json
{
  "announcement": { "text": "string, may be empty, may contain newlines" },
  "gameServers": [
    {
      "name": "Office 24/7",
      "game": "cs2",
      "info": "de_dust2",
      "addresses": ["192.168.130.40:27015"],
      "online_players": 7,
      "max_players": 12,
      "capabilities": {
        "player_count": true,
        "player_names": true,
        "player_score": true,
        "player_team": false
      },
      "players": [{ "name": "FiNT", "score": 21, "info": "CT" }],
      "last_update": "2026-10-03T18:40:12Z"
    }
  ]
}
```

Rules the signage copies from the Vue code:

- `game` is a free-form key. Known keys and aliases: `cs2`, `csgo`, `css`,
  `csstrike`, `satisfactory`, `factorygame`, `garrysmod`, `gmod`, `xonotic`,
  `scpsl`, `mc`, `minecraft`, `quake3`, `dods`, `factorio`, `openarena`,
  `openttd`, `supertuxkart`, `svencoop`, `teamspeak`, `ts3`, `tf2`. Map them
  through `projectile_keys` in `content/games.yaml`; unknown keys get a grey
  card with the raw key as the game name.
- Player count text: `online / max` when `capabilities.player_count` is
  true, otherwise `max: N`.
- Sort by the integer after the last dot of `addresses[0]`'s host part;
  servers without a parsable address sort last.
- The desktop view polls every 10 seconds, the wall every 5. The signage
  caches the bundle for `PROJECTILE_CACHE_SECONDS` (default 10) and never
  hits the API more often than that, however many kiosks are open.
- Projectile's own `announcement.text` is shown on its wall. The signage
  does not mirror it by default; `PROJECTILE_MIRROR_ANNOUNCEMENT=true` turns
  it into an info-level bar so organizers can keep typing in one place.

### Write endpoints (not used)

`/api/admin/announcement` (GET, PUT `{text}`, DELETE) and
`/api/admin/servers` (GET, DELETE `/{id}`) take an `Authorization: Key <password>`
header. The signage never calls them.

## 5. Bracket

Ctrl-Alt-GG fork of evroon/bracket. FastAPI under `/api`, React frontend,
hosted at `bracket.ctrl-alt-gg.hu` behind nginx (see the `bracket` Ansible
role). Tournament sign-up for attendees happens here (Care says the captain
must click the final sign-up action), and the public dashboard has a "Big
screen" mode of its own. The signage shows a compact summary and sends people
to Bracket for the full picture.

### Which tournament

`BRACKET_TOURNAMENT_ID` pins one tournament. When unset, the signage takes
the first tournament from `GET /api/tournaments?filter_=OPEN` (unauthenticated:
returns open tournaments, running ones first, then by start time).

### Read endpoints

All three accept no token as long as the tournament is `OPEN` or has
`dashboard_public` set; otherwise they answer 401 and the slide shows its
empty state.

| Endpoint | Returns | Used for |
|---|---|---|
| `GET /api/tournaments?filter_=OPEN` | `{ "data": [Tournament] }` | Picking the tournament, its name and `start_time` |
| `GET /api/tournaments/{id}/stages` | `{ "data": [StageWithStageItems] }` | Matches: stages contain stage items, which contain rounds, which contain matches |
| `GET /api/tournaments/{id}/teams` | `{ "data": [FullTeamWithPlayers] }` | Team names by id when a match's inputs only carry `team_id` |

Shapes (from `backend/bracket/models/db/`):

```json
Tournament {
  "id": 3, "club_id": 1, "name": "CS2 Autumn 2026",
  "created": "...", "start_time": "2026-10-03T18:00:00Z",
  "duration_minutes": 30, "margin_minutes": 5,
  "dashboard_public": true, "dashboard_endpoint": "cs2",
  "logo_path": null, "players_can_be_in_multiple_teams": false,
  "status": "OPEN"
}

Match {
  "id": 41, "round_id": 7, "created": "...",
  "start_time": "2026-10-03T18:30:00Z",
  "duration_minutes": 30, "margin_minutes": 5,
  "custom_duration_minutes": null, "custom_margin_minutes": null,
  "stage_item_input1_id": 11, "stage_item_input2_id": 14,
  "stage_item_input1_score": 0, "stage_item_input2_score": 0,
  "stage_item_input1_conflict": false, "stage_item_input2_conflict": false,
  "stage_item_input1": { "id": 11, "slot": 1, "team_id": 5, "team": { "id": 5, "name": "Headshot Heroes", "...": "..." }, "winner_from_stage_item_id": null, "winner_position": null, "points": "0.0", "wins": 0, "draws": 0, "losses": 0 },
  "stage_item_input2": { "id": 14, "slot": 4, "team_id": null, "winner_from_stage_item_id": 2, "winner_position": 1, "...": "..." }
}
```

The example values are illustrative; the field names and types are from the
models. All datetimes are UTC with a `Z` suffix. Convert to
`Europe/Budapest` for display.

### Deriving match status

Copy `matchStatus()` from `frontend/src/app/utils.ts`:

1. If either score is non-zero, or the match is marked scored by the API
   (`isScored`: `stage_item_input1_score != 0 or stage_item_input2_score != 0`),
   status is `finished`.
2. Else if `stage_item_input1` or `stage_item_input2` is null, status is
   `waiting` (teams not known yet). Do not show these.
3. Else if `start_time` is set and `start_time <= now < start_time + duration_minutes`,
   status is `live`.
4. Else `scheduled`.

Team label for an input: `input.team.name` when present; otherwise
"Winner of match N" style text is not available from the API alone, so render
the Hungarian/English pair "TBD" / "TBD" and let Bracket show the detail.

Flatten stages -> stage_items -> rounds -> matches, sort by `start_time`
(nulls last), then pick: live (all), upcoming (`scheduled`, first four),
results (`finished`, last three by start time).

### Cadence and caching

Poll at most every `BRACKET_CACHE_SECONDS` (default 15). The stages payload
can be a few hundred kilobytes for a big bracket; cache it as parsed Python,
not as raw JSON, and keep a "last good" copy for an hour so a Bracket restart
does not blank the slide.

## 6. Streams

Django 6 directory for MediaMTX streams, intentionally anonymous and
network-private. The signage calls its read-only API.

`GET {STREAMS_API_BASE_URL}/streams/` (the base URL ends in `/api/v1`):

```json
{
  "source": { "status": "fresh", "observed_at": "2026-10-03T19:02:10+00:00", "age_seconds": 3.2, "failure_count": 0 },
  "results": [
    {
      "id": "0192f0a1-...", "display_name": "Main stage", "description": "",
      "effective_name": "Main stage", "status": "live",
      "available": true, "online": true, "audio_only": false,
      "tracks": [{ "codec": "H264", "width": 1920, "height": 1080, "sample_rate": null, "channel_count": null }],
      "observed_at": "2026-10-03T19:02:10+00:00", "stale": false,
      "watch_url": "https://streams.ctrl-alt-gg.hu/streams/0192f0a1-.../",
      "thumbnail_url": "https://streams.ctrl-alt-gg.hu/streams/0192f0a1-.../thumbnail/",
      "hls_url": "https://media.../hls/live/mainstage/index.m3u8"
    }
  ]
}
```

- `source.status` is `fresh`, `stale` or `unavailable`. When not `fresh`,
  mark the slide footer as possibly stale; still show the last list.
- Only `status == "live"` channels go on the wall. `effective_name` is the
  name to show (`display_name` falls back to the path name without `live/`).
- `thumbnail_url` is served by Streams with short cache headers. The signage
  proxies it (`/display/thumb/<stream_id>/`) with a 20-second cache so kiosks
  on a restricted VLAN only need to reach the signage host.
- Poll at most every `STREAMS_CACHE_SECONDS` (default 15).

Streams is also the stylistic reference for this repo's Django code:
Python 3.14, `uv`, `ruff` with line length 100 and the rule set
`E F I N UP B SIM DJ RUF`, `django-environ`, settings split into
`base/development/production/local`, `src/` layout with a `config` package,
`django-tailwind-cli`, `drf-spectacular`, `django-health-check`, gunicorn,
non-root Docker images published to GHCR on `v*` tags with provenance
attestations. `docs/spec.md` says where the signage deviates (no Celery, no
MinIO).

## 7. Network services

Ansible for the venue infrastructure. What matters for the signage:

- Services VLAN 130 hosts DNS (`192.168.130.1`, `.53`, `.54`), the SSH jump
  hosts, TACACS and the Docker hosts for Bracket and MediaMTX. The signage
  host belongs here too, deployed with the same `base`, `users`, `docker` and
  `reverse_proxy` roles (the `bracket` role is the closest template: Compose
  stack on loopback ports behind nginx with TLS).
- Unbound treats `ctrl-alt-gg.hu` as a private domain, so `*.ctrl-alt-gg.hu`
  names resolve to venue addresses on site. Kiosks and the signage host must
  use the venue DNS (DHCP default); hard-coded public resolvers break every
  internal name.
- Access VLANs 140 to 150 are for attendees, 132 is wireless, 128 management.
  Kiosk players (the mini PCs or Raspberry Pis behind the TVs) should get
  reservations in the services VLAN so the firewall rules stay simple.
- TLS certificates are provisioned manually to
  `/etc/letsencrypt/live/<domain>/`; the roles fail if they are missing. The
  signage uses `signage.ctrl-alt-gg.hu` (verify on site) and expects the
  same.
- Nothing here is called at runtime.

## 8. Conventions inherited from the family

1. Hungarian is the source language, English the second. Content is
   bilingual data (separate `hu` and `en` fields), while UI chrome strings
   go through Django's translation machinery.
2. Prose rules from the homepage apply to everything: no em dashes, no en
   dashes, no ellipsis character, no curly quotes, no non-breaking spaces,
   informal Hungarian ("te"), second person, present tense, no filler
   superlatives, no emoji in body text. `scripts/render_content.py`
   enforces the glyph rules on content; CI runs it.
3. Tailwind CSS v4 syntax only (`@import "tailwindcss"`, `@theme`,
   `@source`, `@custom-variant`). Never commit compiled CSS.
4. Pin versions in one place and read them from there (`pyproject.toml`,
   `uv.lock`, `.python-version`, the Dockerfile); never repeat them in docs.
5. GPL-3.0 license, like Streams and this repository already.
6. Every deployable builds to a non-root OCI image on GHCR; the venue can
   run everything with no internet.

## 9. Configuring the connections

Connection settings are not environment variables. Each upstream has one
row in the admin under Signage, Integrations (created by the initial
migration):

| Field | Meaning |
|---|---|
| Enabled | Off by default. A disabled integration drops its slides from the rotation and the overview lists them as disabled. |
| Base URL | API root without a trailing slash, for example `https://servers.ctrl-alt-gg.hu/api`, `https://bracket.ctrl-alt-gg.hu/api`, `https://streams.ctrl-alt-gg.hu/api/v1` |
| Authentication | None, HTTP Basic (username and password), Bearer token, or a custom header with a token |
| Verify TLS, CA bundle | Keep verification on; point the bundle at the venue CA when the certificates are private |
| Connect and read timeout | Seconds; defaults 2 and 4 |
| Cache seconds | Minimum time between upstream calls, however many kiosks poll |
| Tournament id | Bracket only; empty picks the first open tournament |
| Mirror announcement | Projectile only; shows its announcement as an info bar |

Behaviour on failure is the same for all three: the last good response is
kept for `SIGNAGE_LAST_GOOD_SECONDS` (default 3600, an environment variable
because it is a deployment choice, not an event choice) and shown flagged
as stale; after that the slide shows its `empty` text. The room never sees
a stack trace, a spinner or the word "error".
