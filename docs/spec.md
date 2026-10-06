# Build specification: Ctrl-Alt-GG Signage

A Django application that renders the text in `content/` on the organizers'
background (`assets/background.svg`) for the TVs at the LAN party, mixes in
live data from the sibling systems, and gives organizers a plain Django admin
to steer it. This document is written for an AI coding agent: the decisions
are made, the contracts are explicit, and every milestone ends in a check
the agent can run. Read `AGENTS.md` first, then this file, then
`docs/design.md` (visuals), `docs/integrations.md` (upstreams) and
`docs/content.md` (copy).

## 0. Scope

In scope:

- `/display/<screen>/`: the kiosk page, 1920x1080 stage, rotating slides.
- `/display/<screen>/bundle/`: JSON the page polls; server-rendered slide HTML.
- `/admin/`: Django admin for the Event, Screens, Slides, Schedule, Announcements.
- `manage.py loadcontent`: imports `content/*.yaml`.
- Live slides: schedule now/next, countdown, Projectile servers, Bracket
  tournament, Streams live channels.
- Docker image, Compose stack, CI, kiosk runbook.

Out of scope (do not build): user accounts beyond Django staff, a public
internet deployment, video playback, audio, a custom admin theme, a
JavaScript framework, mobile layouts, light mode, editing Projectile or
Bracket data, scraping Care.

## 1. Decisions

These are settled. Do not open them again; if one proves impossible, write
the reason in the PR and pick the closest alternative.

| Topic | Decision | Why |
|---|---|---|
| Runtime | Python 3.14, Django 6.x, `uv`, `ruff` | Same as `Ctrl-Alt-GG/streams`; one toolchain for the family |
| Project layout | `src/config` (settings, urls, wsgi, gunicorn) and one app `src/signage` | Mirrors Streams; one app keeps imports flat |
| Settings | `django-environ`, split `base/development/production/local` | Mirrors Streams |
| Database | `DATABASE_URL`; SQLite file in development, Postgres in Compose | Convention; the data is tiny |
| Cache | `FileBasedCache` at `/tmp/signage-cache` in production, `LocMemCache` in development | Shared across gunicorn workers without Redis |
| Background jobs | None. Upstreams are fetched on request through the cache | Celery would add three containers for four HTTP calls |
| Templates and CSS | Django templates, Tailwind CSS v4 through `django-tailwind-cli`, one source file `src/signage/static_src/app.css` | Mirrors Streams; `@source` scans `templates/**/*.html` |
| Client code | One vanilla JavaScript file, `static/signage/player.js`, no bundler, under 400 lines | Kiosks run one page for 18 hours; less is safer |
| Slide HTML | Rendered server-side per language and shipped inside the bundle JSON | One templating system, Tailwind sees every class |
| QR codes | `segno`, SVG, generated server-side, inlined | Works offline, no image pipeline |
| HTTP client | `httpx` with explicit timeouts | Same as Streams |
| Inline marks in copy | `markdown-it-py` in "zero" preset with only `emphasis` (bold) and `backticks` enabled, output escaped | Bold and code are all the copy uses |
| Time | `TIME_ZONE = "Europe/Budapest"`, `USE_TZ = True`, UTC in the database | Display times are venue local |
| Languages | `LANGUAGES = [("hu", "Magyar"), ("en", "English")]`; UI chrome through `gettext`; content in explicit `_hu` and `_en` columns | Content is data, not translation strings |
| Access | Display and bundle anonymous; admin for `is_staff`; whole app on the venue network only | Nothing here is secret except Wi-Fi, which Spawn already prints |
| API | DRF with `drf-spectacular`, only the endpoints in section 10 | Consistency with Streams without inventing clients |
| Fonts and icons | Vendored into static files at build time; never fetched from the internet at runtime | The venue may be offline |
| Images | `python:3.14-slim`, non-root uid 10001, published to `ghcr.io/ctrl-alt-gg/signage-web` on `v*` tags | Mirrors Streams |

## 2. Target repository layout

```
signage/
  AGENTS.md  README.md  LICENSE
  pyproject.toml  uv.lock  .python-version  manage.py
  .env.example  compose.yaml  compose.local.yaml
  docker/web.Dockerfile
  .github/workflows/ci.yml  .github/workflows/publish.yml
  assets/background.svg                 # the artwork, served as static "signage/background.svg"
  content/*.yaml                        # the copy; see docs/content.md
  docs/                                 # this folder
  scripts/render_content.py             # YAML lint and docs/content.md renderer
  scripts/screenshots.py                # Playwright: every slide, both languages, safe-area check
  src/
    config/
      __init__.py  urls.py  wsgi.py  asgi.py  gunicorn.py
      settings/__init__.py  base.py  development.py  production.py  local.py
    signage/
      __init__.py  apps.py  models.py  admin.py  urls.py  views.py
      api/serializers.py  api/views.py  api/urls.py
      content/lint.py                   # pure functions shared with scripts/render_content.py
      content/loader.py                 # YAML -> models
      integrations/base.py  projectile.py  bracket.py  streams.py
      rendering/bundle.py  phases.py  placeholders.py  qr.py  schedule.py  markup.py
      templates/signage/display.html
      templates/signage/layouts/{hero,list,split,qr,credentials,now_next,schedule,servers,tournament,streams,countdown}.html
      templates/signage/chrome/{clock,announcement_bar,takeover,progress}.html
      templates/signage/admin/overview.html
      static_src/app.css
      static/signage/player.js  static/signage/icons/*.svg  static/signage/fonts/*
      management/commands/loadcontent.py  dumpcontent.py
      migrations/
      tests/  tests/fixtures/{projectile_bundle.json,bracket_tournaments.json,bracket_stages.json,bracket_teams.json,streams_list.json}
    locale/hu/LC_MESSAGES/django.po
```

`STATICFILES_DIRS = [("signage", BASE_DIR / "assets")]` publishes
`assets/background.svg` as `signage/background.svg` without copying it.

## 3. Domain model

All models live in `src/signage/models.py`. Bilingual text is two columns,
`<field>_hu` and `<field>_en`; a `BilingualMixin.text(field, lang)` helper
returns the right one with Hungarian fallback. Every model has
`created_at`, `updated_at`.

### Event (exactly one row)

| Field | Type | Notes |
|---|---|---|
| `name`, `tagline` | CharField | "Ctrl-Alt-GG", "GL&HF, IRL." |
| `starts_at`, `ends_at` | DateTimeField | Venue local in the admin, UTC in the database |
| `timezone` | CharField | IANA name, default `Europe/Budapest` |
| `venue_name`, `venue_address` | CharField | |
| `venue_lat`, `venue_lng` | DecimalField, nullable | |
| `entrance_note_*`, `parking_*`, `assembly_point_*` | TextField | bilingual |
| `wifi_ssid`, `wifi_password` | CharField, blank allowed | |
| `wifi_security` | CharField choices `WPA`, `WEP`, `nopass` | |
| `wifi_note_*` | CharField | bilingual |
| `links` | JSONField | `{key: url}`; keys validated against the list in `content/event.yaml` |
| `email` | EmailField | |
| `organizers` | JSONField | list of strings |
| `phase_mode` | CharField choices `manual`, `auto` | default `manual` |
| `current_phase` | ForeignKey Phase, nullable | used when manual |

Enforce the single row with a `CheckConstraint(pk=1)` style guard
(`id` default 1, `save()` forces `pk=1`) and an `Event.get()` classmethod.

### Phase

`key` (slug, unique), `name_hu`, `name_en`, `starts` (TimeField),
`day_offset` (SmallInteger, default 0), `order` (SmallInteger).

### Game

`slug` (unique), `name`, `short`, `hosted` (bool), `tournament` (bool,
default false), `projectile_keys` (JSONField list), `color_bg`, `color_text`
(7-char hex).

### ScheduleEntry

`time` (TimeField), `day_offset`, `type` (choices `play`, `break`,
`highlight`), `game` (FK Game, nullable), `label`, `title_*`, `note_*`
(blank allowed), `order`. Property `starts_at` = `Event.starts_at` date
plus `day_offset` days at `time`, in the event time zone, returned as an
aware UTC datetime.

### Slide

| Field | Type | Notes |
|---|---|---|
| `key` | SlugField, primary key | the YAML `id` |
| `layout` | CharField choices | the eleven layouts in `docs/design.md` |
| `source` | CharField choices | `static`, `live:schedule`, `live:clock`, `live:projectile`, `live:bracket`, `live:streams` |
| `all_phases` | BooleanField | YAML `phases: all` |
| `phases` | ManyToMany Phase | ignored when `all_phases` |
| `duration_seconds` | PositiveSmallInteger | 5 to 120 |
| `bilingual_mode` | choices `alternate`, `stacked` | |
| `priority` | SmallInteger | 0 to 100 |
| `order` | SmallInteger | position in the YAML, tiebreaker |
| `enabled` | BooleanField | default true |
| `valid_from`, `valid_until` | DateTimeField, nullable | optional window |
| `kicker_*`, `title_*`, `body_*`, `footer_*`, `empty_*` | Text, blank allowed | bilingual; `title_hu` required |
| `items` | JSONField | list of `{"hu": "", "en": "", "icon": ""}`; max 6 |
| `columns` | JSONField | split layout: two `{"title": {hu, en}, "items": [...]}` |
| `labels` | JSONField | `columns_labels` or `sections` from the YAML, as given |
| `link_url` | CharField, blank | `wifi` is a magic value for the Wi-Fi QR |
| `link_label_*` | CharField, blank | |
| `link_qr` | BooleanField | |
| `notes` | TextField | author notes, never rendered |
| `origin` | choices `seed`, `admin` | set to `admin` by the admin form on save |

`clean()` runs the same validation as `content/lint.py` (bilingual pairs,
item count, split needs two columns).

### Screen

`slug` (unique), `name`, `enabled`, `refresh_seconds` (default 20, min 5),
`language_mode` (choices `slide` (follow each slide), `hu`, `en`),
`show_clock`, `show_progress` (bools, default true), `slides` (ManyToMany
Slide through `ScreenSlide(order)`; empty means every slide that matches
the phase), `notes`.

### Announcement

`text_hu`, `text_en`, `level` (choices `info`, `warning`, `urgent`),
`takeover` (bool), `starts_at` (default now), `ends_at` (nullable: open
ended), `enabled`, `screens` (ManyToMany Screen, empty means all),
`template` (FK AnnouncementTemplate, nullable), `created_by` (FK user,
nullable). Property `is_active(now)`.

### AnnouncementTemplate

`key` (unique), `level`, `takeover`, `text_hu`, `text_en`. Property
`placeholders` extracts `{names}` from the text.

## 4. Content pipeline

`python manage.py loadcontent [--overwrite] [--only event|phases|games|schedule|slides|announcements]`

1. Read `content/*.yaml` with `yaml.safe_load`. Run `content/lint.py`
   checks first; stop on the first error with the file and path.
2. Upsert by natural key: `Event` pk 1, `Phase.key`, `Game.slug`,
   `ScheduleEntry (time, day_offset, title_hu)`, `Slide.key`,
   `AnnouncementTemplate.key`.
3. Create missing rows. Update existing rows only when `origin == "seed"`
   (slides) or `--overwrite` is given. Print one line per skipped
   admin-edited row.
4. `phases: all` sets `all_phases=True` and clears the M2M.
5. The command is idempotent: running it twice changes nothing and prints
   "0 created, 0 updated".
6. `scripts/render_content.py` imports its validators from
   `src/signage/content/lint.py` (add `src` to `sys.path` in the script).
   The script stays runnable without Django installed; `lint.py` imports
   nothing from Django.

`python manage.py dumpcontent --out content/` writes the current rows back
into the same YAML shape, so admin edits made during an event can be
committed afterwards. Build this in milestone 6.

## 5. Phases

`rendering/phases.py: resolve_phase(event, now) -> Phase`

- `manual`: return `event.current_phase`, or the first phase by `order`
  when unset.
- `auto`: for each phase compute its boundary as `event.starts_at` date
  plus `day_offset` at `starts`, in the event time zone. Return the phase
  with the latest boundary at or before `now`. Before the first boundary
  return the first phase; after `event.ends_at` return the last phase.

The admin shows the resolved phase and a row of "Set phase" buttons that
switch to manual with that phase in one click.

## 6. Slide selection and the bundle

`GET /display/<screen_slug>/bundle/` returns JSON:

```json
{
  "version": "3f2a9c1d7b0e4a66",
  "generated_at": "2026-10-03T18:40:12+02:00",
  "screen": { "slug": "main", "name": "Main hall", "refresh_seconds": 20, "show_clock": true, "show_progress": true },
  "phase": { "key": "play", "name": { "hu": "Játék", "en": "Play" } },
  "clock": { "now": "2026-10-03T18:40:12+02:00", "timezone": "Europe/Budapest" },
  "announcement": null,
  "passes": [
    { "slide": "welcome", "layout": "hero", "lang": "both", "duration_ms": 12000, "html": "<section class=\"slide slide-hero\" ...>...</section>" },
    { "slide": "house_rules", "layout": "list", "lang": "hu", "duration_ms": 20000, "html": "..." },
    { "slide": "house_rules", "layout": "list", "lang": "en", "duration_ms": 20000, "html": "..." }
  ],
  "warnings": []
}
```

`announcement`, when present:

```json
{ "id": 12, "level": "warning", "takeover": false, "text": { "hu": "...", "en": "..." }, "ends_at": "2026-10-03T19:00:00+02:00" }
```

Selection algorithm (`rendering/bundle.py: build_bundle(screen, now)`):

1. Resolve the phase (section 5).
2. Candidates: `Slide.objects.filter(enabled=True)`, in the phase
   (`all_phases` or `phases` contains it), inside `valid_from`/`valid_until`
   when set. If the screen lists slides, intersect and use the screen order;
   otherwise order by `-priority, order`.
3. Drop a live slide whose integration is disabled by configuration
   (`docs/integrations.md` section 9). Add a warning
   `"servers: disabled, PROJECTILE_API_BASE_URL is empty"`.
4. Drop `live:clock` slides whose target (`event.starts_at`) has passed.
5. Resolve placeholders (`rendering/placeholders.py`): `{wifi_ssid}`,
   `{wifi_password}`, `{wifi_note}`, `{venue_name}`, `{venue_address}`,
   `{starts_at_time}` (HH:MM), `{starts_at_date}` (`2026. 10. 03.` in
   Hungarian, `3 October 2026` in English), `{assembly_point}`, `{email}`.
   If any rendered text still contains `{`, `}` or the string `CHANGE-ME`,
   drop the slide and add a warning naming the slide and the placeholder.
6. Render each remaining slide with its layout template, once per language
   for `alternate`, once with `lang="both"` for `stacked`. The template
   context is a view model (section 8) plus `lang`, `event`, `screen`.
7. `version` is the first 16 hex characters of SHA-256 over the
   concatenation of: phase key, each pass's slide key and `updated_at`, the
   announcement id and `updated_at`, and each live view model's `data_hash`.
   Respond `304 Not Modified` when `If-None-Match` equals the version; set
   `ETag` and `Cache-Control: no-store`.
8. Announcement: enabled, `starts_at <= now`, `ends_at` null or `> now`,
   for this screen or for all screens. Pick the highest level
   (`urgent > warning > info`), then the most recently created.

An empty `passes` list is allowed (for example, nothing matches the
phase); the player then shows the field with the clock only.

## 7. The player (`static/signage/player.js`)

Behaviour, in order of precedence:

1. On load: read `data-bundle-url`, `data-refresh-seconds` and
   `data-preview` from `<body>`. Compute `--stage-scale` (see
   `docs/design.md` section 2) now and on `resize`.
2. Fetch the bundle with `If-None-Match`. On 200: store it, replace the
   pass list, keep the current position by `slide` key when it still
   exists, otherwise restart at index 0. On 304: nothing. On network error
   or 5xx: keep the current bundle, retry with exponential backoff (2, 4,
   8, 16, 32, then every 60 seconds), show the offline dot after 60 seconds
   without success.
3. Show passes in order. Each pass is injected into an offscreen container,
   then crossfaded in (400 ms) while the previous fades out. After
   `duration_ms`, advance. Wrap around at the end.
4. The clock renders `HH:MM` from the client clock in the bundle's time
   zone (use `Intl.DateTimeFormat` with `timeZone`), updated every second.
   The language pill shows the current pass language in `alternate` passes.
5. Progress bar: CSS transition over `duration_ms`, reset at each pass.
6. Announcement bar: when `announcement` is present and `takeover` is
   false, render `chrome/announcement_bar.html`'s structure from the JSON
   (the bar is the one piece of HTML built on the client, kept to a
   template literal with escaped text) and add `has-bar` on the stage so
   layouts shrink. When `takeover` is true, show the takeover card instead
   of passes, keep the clock, freeze the rotation index, and resume when
   the bundle no longer carries it.
7. Countdown passes carry `data-target` on their root; the player updates
   the digits every second and removes the pass when the target passes.
8. Live dots pulse with CSS only.
9. Preview mode: `?preview=<slide_key>&lang=<hu|en|both>` makes the server
   return a bundle with that single pass regardless of phase and the player
   never advances. `?phase=<key>` overrides the phase for staff users or
   when `DEBUG`. Preview never changes anything in the database.
10. Hygiene: `location.reload()` once every 6 hours, only at a pass boundary
    and only if the last bundle fetch succeeded.
11. No `console.log` in the shipped file; errors go to `console.error`
    only. No external requests except the bundle and thumbnail proxy.

## 8. Live data

`integrations/base.py`:

```python
@dataclass(frozen=True)
class Result[T]:
    data: T | None
    stale: bool
    fetched_at: datetime | None
    error: str | None

class Integration[T]:
    key: str                    # "projectile", "bracket", "streams"
    enabled: bool               # base URL configured
    ttl: int                    # cache seconds from settings
    def fetch(self) -> Result[T]: ...   # cached; never raises
    def _request(self) -> T: ...        # subclass: HTTP + parse, may raise
```

`fetch()` returns the cached parsed value when fresh; otherwise calls
`_request()`, stores it under `signage:<key>` for `ttl` seconds and under
`signage:<key>:last` for 3600 seconds; on any exception logs a WARNING with
the upstream and the exception class, and returns the `:last` value with
`stale=True`, or `Result(None, True, None, "<class>")` when nothing is
cached. Parsing lives in pure functions that take a `dict` and return the
view model, so tests use the fixture JSON files without HTTP.

View models (`dataclasses`, all with `data_hash` property):

- `ScheduleVM`: `now: list[Entry]`, `next: list[Entry]`, `later: list[Entry]`,
  `upcoming: list[Entry]` (current plus next seven). Rules: an entry is
  current from its `starts_at` until the next distinct `starts_at`; after
  the last entry it stays current until `event.ends_at`; before the first
  entry `now` is empty and `next` is the first time slot. Entries that share
  a time are one group.
- `CountdownVM`: `target: datetime`, `passed: bool`.
- `ServersVM`: `servers: list[Server(name, game_slug, game_name, color_bg, color_text, players_text, sort_key)]`,
  `more: int`, `stale: bool`, `announcement: str | None`.
- `TournamentVM`: `name`, `live: list[Match]`, `upcoming: list[Match]`,
  `results: list[Match]`, `stale`; `Match(team1, team2, score1, score2, start_local, status)`.
  Status rules are in `docs/integrations.md` section 5.
- `StreamsVM`: `live: list[Channel(id, name, audio_only, thumbnail_url)]`, `stale`.

Thumbnail proxy: `GET /display/thumb/<uuid>/` fetches the Streams
`thumbnail_url` for that channel id (looked up from the cached list, never
from the query string), caches the bytes for 20 seconds, returns them with
the upstream content type, and answers 404 for unknown ids.

## 9. Admin

Stock Django admin, registered in `admin.py`:

- `EventAdmin`: the changelist redirects to the single object. Fieldsets:
  Event, Venue, Wi-Fi, Links, Phase. A read-only "Resolved phase" field and
  "Set phase" buttons (one small custom template, POST to an admin view).
- `PhaseAdmin`, `GameAdmin`: plain, `list_editable` on `order`, `hosted`.
- `ScheduleEntryAdmin`: ordered by `day_offset, time`; `list_editable`
  on `time`, `type`; shows the computed local `starts_at`.
- `SlideAdmin`: `list_display` key, layout, source, phases, enabled,
  priority, duration; `list_editable` enabled, priority, duration;
  `list_filter` layout, source, phases, enabled; search on titles; actions
  "Enable", "Disable"; per-row links "Preview HU", "Preview EN" that open
  `/display/main/?preview=<key>&lang=<lang>` in a new tab; JSON fields with
  the model `clean()` errors shown inline; saving sets `origin="admin"`.
- `ScreenAdmin`: with an inline for the ordered slides and a "Open display"
  link.
- `AnnouncementAdmin`: `list_display` text (Hungarian, truncated), level,
  takeover, active, window, screens; action "End now" (sets `ends_at=now`);
  a "New from template" admin view: choose a template, fill its
  placeholders in a generated form, pick a duration (10 min, 30 min, 60 min,
  until ended), pick screens, save.
- `AnnouncementTemplateAdmin`: plain.
- Overview page at `/admin/signage/overview/` (staff only): resolved phase
  and mode, active announcements, each screen with a scaled live iframe
  (480x270) and its URL, integration status table (enabled, fresh or stale,
  last fetch, last error), and the bundle `warnings` for each screen.

## 10. API

Under `/api/v1/`, read-only, anonymous, JSON only:

- `GET /api/v1/screens/<slug>/bundle/`: the same payload as the display bundle.
- `GET /api/v1/schedule/`: `ScheduleVM` as JSON plus the raw entries.
- `GET /api/v1/phase/`: the resolved phase.
- `GET /api/v1/announcements/active/`: active announcements for all screens.

`/api/schema/` and `/api/docs/` for staff only, as in Streams. `/health/`
from `django-health-check` with the database and cache checks.

## 11. Settings and environment

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` | production image sets `config.settings.production` |
| `DJANGO_SECRET_KEY` | development placeholder | required in production |
| `DJANGO_DEBUG` | `false` | |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | comma separated |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | used in absolute URLs on the overview page |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | Postgres in Compose |
| `CACHE_DIR` | `/tmp/signage-cache` | production file cache |
| `TIME_ZONE` | `Europe/Budapest` | |
| `SIGNAGE_DEFAULT_SCREEN` | `main` | `/display/` redirects here |
| `LOG_LEVEL` | `INFO` | |
| `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT` | `2`, `4`, `30` | |
| integration variables | see `docs/integrations.md` section 9 | |

Security headers: `SECURE_*` as in Streams for production,
`X_FRAME_OPTIONS = "SAMEORIGIN"` (the overview iframes), CSP
`default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'`
through Django's CSP middleware; no inline scripts, no inline styles except
the few `style=` attributes the stage needs (allow `'unsafe-inline'` for
`style-src-attr` only). The admin is reachable only through nginx rules
on the venue network; do not add authentication to the display.

## 12. Tests

`pytest` with `pytest-django`, settings `config.settings.development`,
database SQLite in memory. The following tests must exist and pass:

1. `test_lint`: `content/lint.py` rejects a missing `en`, a seventh item,
   a split with one column, an unknown phase, an em dash.
2. `test_loadcontent`: loads the real `content/` files; counts match the
   YAML; a second run creates and updates nothing; an admin-edited slide is
   skipped without `--overwrite` and updated with it.
3. `test_phases`: manual and auto resolution, including before the first
   boundary, across midnight (`morning` at 05:30 on day 1), and after
   `ends_at`.
4. `test_schedule_vm`: now/next/later at 15:00 (nothing now), 20:10 (two
   entries now), 23:50 (next is 00:00 on day 1), 06:30 (last entry stays
   current), and after `ends_at`.
5. `test_placeholders`: every placeholder resolves; a slide with
   `CHANGE-ME` is dropped with a warning naming it; `{starts_at_date}` is
   Hungarian-formatted in `hu`.
6. `test_bundle`: phase filtering, screen slide lists, priority order,
   alternate expansion to two passes, stacked to one, ETag and 304,
   announcement precedence, takeover flag, disabled integration warning.
7. `test_integrations`: each parser against its fixture; `fetch()` returns
   stale last-good data when `_request` raises; returns `data=None` when
   nothing is cached; never raises.
8. `test_templates`: every layout renders for every slide in `content/`
   in both languages with no `TemplateSyntaxError` and no unresolved
   `{` in the output.
9. `test_views`: display page 200, bundle 200 and 304, preview returns one
   pass, unknown screen 404, thumbnail proxy 404 for unknown id.
10. `scripts/screenshots.py` (not in pytest): Playwright with the
    preinstalled Chromium at 1920x1080; for every slide and language writes
    `docs/screenshots/<slide>-<lang>.png`, asserts the safe-area and
    overflow rules from `docs/design.md` section 9, exits non-zero on a
    violation. CI runs it when Chromium is available and uploads the PNGs
    as an artifact; the repo commits them when templates change.

## 13. Tooling and CI

`pyproject.toml` copies the Streams `[tool.ruff]` block (line length 100,
rules `E F I N UP B SIM DJ RUF`, `DJ001` ignored, migrations exempt from
`E501` and `RUF012`). Dependencies: `django`, `django-environ`,
`djangorestframework`, `drf-spectacular`, `drf-spectacular-sidecar`,
`django-tailwind-cli`, `django-health-check`, `httpx`, `segno`,
`markdown-it-py`, `pyyaml`, `psycopg[binary]`, `gunicorn`. Dev group:
`ruff`, `pytest`, `pytest-django`, `playwright`.

`.github/workflows/ci.yml` (on pull requests and pushes to `main`):

```
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run python scripts/render_content.py --check
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py tailwind build
uv run pytest
```

`.github/workflows/publish.yml` (on `v*` tags): build
`docker/web.Dockerfile`, push `ghcr.io/<owner>/signage-web:<tag>` and
`:latest`, attach provenance, like the Streams workflow with a single
component.

## 14. Docker, Compose, kiosk

- `docker/web.Dockerfile`: copy the Streams `web.Dockerfile`, change the
  label, keep `compilemessages -l hu` and `tailwind build --force` at build
  time, run `collectstatic` in the Compose `setup` service.
- `compose.yaml`: `postgres` (18), `setup` (migrate, collectstatic,
  `loadcontent`), `web` on `127.0.0.1:8000`, both app services
  `read_only` with `tmpfs` on `/tmp` (the file cache lives there),
  `no-new-privileges`, `cap_drop: ALL`, health check on `/health/`.
  Static files are served by nginx from a shared volume (`./data/static`),
  not by MinIO; the family's `reverse_proxy` Ansible role fronts it.
- `compose.local.yaml`: SQLite, `runserver`, `tailwind watch`.
- `docs/kiosk.md` (write in milestone 5): Chromium command line for a
  Linux mini PC or Raspberry Pi:
  `chromium --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --check-for-update-interval=31536000 --autoplay-policy=no-user-gesture-required https://signage.ctrl-alt-gg.hu/display/main/`,
  `xset s off -dpms` and `unclutter -idle 1`, a systemd user unit that
  restarts the browser, DHCP for DNS and NTP from the venue, a static
  reservation in the services VLAN, and the TV set to 1920x1080 at 100
  percent scaling with overscan off.

## 15. Milestones

Each milestone is one PR. The acceptance list is the PR checklist. Do not
start the next milestone with a red check in the current one.

### M0: Skeleton

Build: `uv` project, Django project and app, settings split, `ruff`,
`pytest` wiring, `/health/`, admin, `manage.py tailwind` configured with
`app.css` carrying the tokens from `docs/design.md` section 3, CI workflow,
`.env.example`, `README.md` quickstart.

Accept: `uv run python manage.py check` passes; `uv run ruff check .` and
`uv run ruff format --check .` pass; `uv run python manage.py tailwind build`
produces CSS; `uv run pytest` runs zero or more tests green; CI green.

### M1: Content model and loader

Build: models from section 3 with migrations; `content/lint.py` and the
rewired `scripts/render_content.py`; `loadcontent`; admin registrations
from section 9 except the overview and the template view; tests 1 and 2.

Accept: `uv run python manage.py migrate && uv run python manage.py loadcontent`
prints 25 slides, 17 schedule entries, 7 phases, 27 games, 13 templates
created; a second run prints zeros; admin lists everything;
`python3 scripts/render_content.py --check` passes.

### M2: Display and static layouts

Build: `display.html`, the stage, background, clock, progress, the
`hero`, `list`, `split`, `qr`, `credentials` layouts, placeholder
resolution, the bundle endpoint with ETag, `player.js`, preview mode,
phases (section 5), screens; tests 3, 5, 6 (static parts), 8, 9.

Accept: `/display/main/` rotates the static slides of the resolved phase
in both languages; `?preview=house_rules&lang=hu` shows one slide; the
`wifi` slide is dropped with a warning while the SSID is `CHANGE-ME`;
`scripts/screenshots.py` passes the safe-area check for every static
slide; PNGs committed under `docs/screenshots/`.

### M3: Schedule, countdown, announcements

Build: `ScheduleVM`, `now_next`, `schedule` and `countdown` layouts,
`CountdownVM`, announcements (model is from M1; add the bar, the takeover,
the "New from template" admin view, the "End now" action); tests 4 and
the announcement parts of 6.

Accept: at a faked 20:10 the `now_next` slide shows both 20:00 entries
under "Most"; an urgent takeover replaces the rotation within one refresh
and the rotation resumes at the same slide afterwards; a warning bar
pushes content up without clipping (screenshot check).

### M4: Integrations

Build: `integrations/*`, the `servers`, `tournament`, `streams` layouts,
the thumbnail proxy, fixtures, the overview page's integration table;
test 7.

Accept: with the fixtures served by a local stub (`pytest` `httpx`
transport mock or `respx`), all three slides render; with the stub
returning 500 the slides show last-good data flagged stale, then the
empty state after the last-good TTL; with base URLs empty the slides are
absent and listed as disabled on the overview page.

### M5: Ship

Build: `docker/web.Dockerfile`, `compose.yaml`, `compose.local.yaml`,
`publish.yml`, `docs/kiosk.md`, the overview page completed.

Accept: `docker compose up` on a clean machine serves `/display/main/`
on `127.0.0.1:8000` after `setup` finishes; the image runs read-only as
uid 10001; `/health/` is green; a tag push publishes the image.

### M6: Polish

Build: `dumpcontent`; Hungarian translations for all chrome strings
(`makemessages`, fill `django.po`, `compilemessages` in the image);
reduced-motion handling; the 6-hour reload; final screenshot pass of every
slide in both languages committed to `docs/screenshots/`.

Accept: `uv run python manage.py makemessages -l hu` shows no untranslated
chrome strings; screenshots updated; CI green.

## 16. Definition of done (every PR)

- CI green: ruff, format, content check, Django checks, migrations check,
  Tailwind build, pytest.
- No generated files committed: compiled CSS, `staticfiles/`, `db.sqlite3`,
  `.django_tailwind_cli/`, `node_modules/`, `__pycache__/`.
- No em dashes, en dashes, ellipsis characters or curly quotes anywhere in
  the diff (run the sweep from `AGENTS.md`).
- Every new user-facing chrome string wrapped in `gettext` and translated
  in `locale/hu`.
- Every new slide, layout or setting documented: `docs/content.md`
  regenerated when `content/` changed, `docs/design.md` when a layout
  changed, `docs/spec.md` section 11 when a setting was added.
- `AGENTS.md` updated when a convention changed.
- Screenshots regenerated when templates or CSS changed.

## 17. Open questions for the organizers

None of these block the build; the admin fields exist for all of them.

1. The event date and closing time (`event.starts_at`, `event.ends_at`).
   The homepage pointed at 2026-10-03 when the content was read.
2. The Wi-Fi SSID (`event.wifi_ssid`).
3. The fire assembly point text (`event.assembly_point_*`).
4. Base URLs on the venue network for Projectile, Bracket and Streams, and
   the signage hostname (`signage.ctrl-alt-gg.hu` is assumed).
5. Whether Projectile's announcement should be mirrored on the signage
   (`PROJECTILE_MIRROR_ANNOUNCEMENT`).
6. How many screens there are and what each should show (one `Screen` row
   each; `main` is the default rotation, a `tournament` screen with only
   `tournament_live`, `now_next` and announcements is the obvious second).
7. Whether a DISTR3CT house rule (smoking area, noise curfew) should be
   added as a slide.
