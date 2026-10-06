# AGENTS.md: Ctrl-Alt-GG Signage

> Canonical guide for AI coding agents (GitHub Copilot, Cursor, Codex, Claude
> and friends) and for humans working on this repository. Read this first.
> The code is the source of truth for everything this file does not state:
> there is no docs folder, and generated files are never committed.

## 1. What this repo is

The digital signage for the Ctrl-Alt-GG LAN party: bilingual (Hungarian
first, English second) slides on the organizers' background artwork, mixed
with live data from the other Ctrl-Alt-GG systems (schedule, game servers,
tournament, streams), steered from a Django admin during the event. It runs
on the venue network only.

Three containers, one per component, plus Postgres:

| Component | Image | Runs |
|---|---|---|
| backend | `docker/backend.Dockerfile`: Python on Debian slim | Django admin (the only management UI), the JSON API, the upstream integrations, the YAML content import |
| frontend | `docker/frontend.Dockerfile`: rootless nginx on Debian | The React 19 + TypeScript + Tailwind CSS v4 display built by Vite. nginx also proxies `/api/`, `/admin/` and `/health/` to the backend, so a kiosk or an organizer sees one origin |
| minio | `docker/minio.Dockerfile`: MinIO built from source on Debian | The S3 bucket holding Django's static files and the uploaded background; browsers load them from here |

Each image contains only what its component needs to run. No alpine
variants anywhere.

## 2. Where things live

| Fact | Lives in |
|---|---|
| Event facts, Wi-Fi, links, organizers, phases | `content/event.yaml` |
| Slide copy | `content/slides.yaml` |
| Schedule rows | `content/schedule.yaml` |
| Games, colours, Projectile aliases | `content/games.yaml` |
| Announcement templates | `content/announcements.yaml` |
| Data model and admin | `src/signage/models.py`, `src/signage/admin.py` |
| YAML import and the prose lint rules | `src/signage/content/` |
| What a screen shows: passes, phases, schedule view | `src/signage/rendering/` |
| The JSON API and its serializers (the frontend contract) | `src/signage/api/` |
| Upstream systems: Projectile, Bracket, Streams | `src/signage/integrations/` |
| Settings, file storage wiring, gunicorn | `src/config/` |
| Stage geometry and the content-safe area | `frontend/src/lib/stage.ts` |
| Layouts, bilingual rendering, design tokens | `frontend/src/layouts/`, `frontend/src/lib/i18n.tsx`, `frontend/src/app.css` |
| Container images and the nginx configuration | `docker/` |
| Stacks and their variables | `compose.yaml`, `compose.local.yaml`, `.env.example` |
| Pipeline | `.github/workflows/pipeline.yml` |
| The background artwork | `assets/background.svg` (never edited) |
| Tool versions | `pyproject.toml`, `uv.lock`, `.python-version`, `frontend/package.json`, `frontend/.nvmrc`, `docker/*.Dockerfile` |

Do not repeat versions or URLs in prose; link to the file that pins them.

## 3. Settled decisions

- Backend: the latest Django. Django plugins and Python libraries first;
  custom code only when neither suffices. What is in use and why is
  visible in `pyproject.toml` and the settings.
- Frontend: the latest React and Tailwind CSS v4 with daisyUI. React
  plugins and TypeScript libraries first. Utilities, not custom CSS; one
  stylesheet, `frontend/src/app.css`, holds the tokens.
- Only the backend talks to other systems. The frontend talks only to the
  backend API. Upstream REST endpoints and credentials are configured in
  the admin (Integration rows); systems without an API are fed through
  the admin by hand.
- Organizers manage everything in the Django admin. Slides, schedule,
  games and event facts load from `content/*.yaml` (`loadcontent` or the
  admin import). Rows are matched by a stable key (slide id, schedule
  `key`, game slug, phase key, template key); a row saved in the admin
  carries `origin=admin` and later imports skip it unless overwrite is
  requested, so a redeploy never undoes an organizer's edit. The
  background SVG is exchangeable in the admin.
- Files: with `STORAGE_ENDPOINT_URL` set, django-storages keeps static
  files and uploads in the S3 bucket and `manage.py ensurestorage` creates
  the bucket with an anonymous-read policy; without it the filesystem
  under `data/` is used (development). The backend never serves static
  files in production.
- Access rights are fixed: the API is read-only and anonymous, the admin
  is staff-only.
- Generated files are git-ignored and never committed:
  `frontend/openapi.yaml`, `frontend/src/api/schema.d.ts`,
  `frontend/dist/`, `*.tsbuildinfo`, `docs/`, `screenshots/`, `data/`.

## 4. Display invariants

- The stage is 1920x1080 and every piece of text stays inside the
  content-safe area, x 96 to 1824 and y 204 to 768
  (`frontend/src/lib/stage.ts`; overridable in Display settings).
- Every slide is bilingual on one pass: Hungarian large, English beneath
  at 0.72em; one-line labels join the two with a middle dot. Hungarian is
  required, English falls back to Hungarian.
- Live slides fall back to last-good data, then to their `empty` text.
  The room never sees an error.
- Nothing is fetched from the public internet by the display: fonts,
  icons and QR codes are bundled or generated.
- Tailwind v4 syntax only (`@import "tailwindcss"`, `@theme`, `@source`).

## 5. How to work

- Content changes go through the YAML files;
  `python3 scripts/render_content.py --check` lints them (both languages
  present, bullet limits, banned typography). Without `--check` it also
  writes a Markdown preview to the git-ignored `docs/content.md`.
- Keep the copy honest to its sources (the homepage and Care). Anything
  only an organizer knows stays `CHANGE-ME` in the seed and is set in the
  admin; the app drops a slide with an unresolved value.
- API changes: edit the serializers, regenerate the schema and the
  TypeScript types (section 7), then adjust the frontend.
- No new framework, bundler, queue or storage service without a line in
  section 3 saying why.
- `.github/workflows/**` changes only when the workflow is the subject of
  the change.

## 6. Conventions

- Python 3.14, Django 6, `uv`, `ruff` (line length 100, rules
  `E F I N UP B SIM DJ RUF`), `src/` layout, settings split
  `base/development/production`, mirrored from `Ctrl-Alt-GG/streams`.
- Frontend: React 19, TypeScript, Vite, Tailwind CSS v4 (`@tailwindcss/vite`)
  with daisyUI components, TanStack Query for the API, openapi-fetch with
  types generated from the backend schema.
- Bilingual content is data: `_hu` and `_en` columns, Hungarian required.
- Hungarian is written natively, informal "te", second person, present
  tense. English is idiomatically independent, not a calque.
- Prose rules from the homepage apply to copy, comments and commit
  messages: no em dashes, no en dashes, no ellipsis character, no curly
  quotes, no non-breaking spaces, no emoji in text, no filler
  superlatives. Hyphen for ranges (`10-15 perc`), three periods for an
  ellipsis, straight quotes.
- Comments state what the code cannot. No narration of the next line.
- Commit messages: imperative subject under 72 characters, a body that
  says why. No model names or tool advertisements in commits.

Sweep before committing:

```bash
git diff --name-only main \
  | grep -v 'scripts/render_content.py' \
  | xargs -r env LC_ALL=C.UTF-8 grep -HnP '[\x{2013}\x{2014}\x{2026}\x{2018}\x{2019}\x{201C}\x{201D}\x{00A0}]'
```

The sweep must print nothing. `scripts/render_content.py` is excluded
because it lists the banned glyphs in order to reject them. Use a UTF-8
locale: under `LC_ALL=C` a byte-wise bracket match flags accented letters
such as `Ó` and `Ü` by mistake.

## 7. Running the project

```bash
uv sync                                    # Python 3.14 and the backend dependencies
uv run python manage.py migrate
uv run python manage.py loadcontent        # content/*.yaml into the database
uv run python manage.py createsuperuser
uv run python manage.py spectacular --file frontend/openapi.yaml --validate
(cd frontend && pnpm install && pnpm openapi)   # TypeScript types from the schema
uv run python manage.py runserver          # admin and API on :8000
(cd frontend && pnpm dev)                  # the display on :5173, proxying the backend
```

Open <http://localhost:5173/> for the display and
<http://localhost:5173/admin/> for the admin (the Vite proxy forwards it,
like nginx does in production). The display route is
`/display/<screen>/`; the root redirects to the default screen.

The whole stack in containers, built from this checkout:
`docker compose -f compose.local.yaml up --build`, then
<http://localhost:8080/>. The published images run with `compose.yaml`
and a `.env` copied from `.env.example`.

## 8. Checks before a commit

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest                              # Django checks, migrations, content lint, schema validity included
uv run python manage.py spectacular --file frontend/openapi.yaml --validate
(cd frontend && pnpm openapi && pnpm typecheck && pnpm test && pnpm build)
(cd frontend && pnpm preview) &            # :4173, proxies the backend on :8000
uv run python scripts/screenshots.py       # safe area, clipping and overflow checks
```

The pipeline runs the same commands, then builds the three images and,
on `main` and `v*` tags, publishes them to GHCR.

## 9. Do-not-touch list

- `assets/background.svg`: the organizers' artwork, stored verbatim.
- Generated files are regenerated, never edited or committed: the OpenAPI
  schema, `frontend/src/api/schema.d.ts`, `frontend/dist/`,
  `screenshots/`, `docs/`.
- `.github/workflows/**` unless the workflow is the subject of the change.
- Content of `LICENSE` (GPL-3.0).

## 10. Definition of done

A change is done when the checks in section 8 pass, the screenshot script
passes for anything that touches layouts or styles, and this file reflects
any changed behaviour or convention. "It renders on my machine" is not
done; the screenshot script and the test suite are.

## 11. Where the other agent files fit

- `.github/copilot-instructions.md`: thin always-loaded pointer to this
  document with the invariants Copilot Chat must never break.
- `.github/PULL_REQUEST_TEMPLATE.md`: the PR checklist.
