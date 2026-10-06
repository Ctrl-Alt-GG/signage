# Ctrl-Alt-GG Signage

Digital signage for the [Ctrl-Alt-GG](https://www.ctrl-alt-gg.hu) LAN party:
bilingual slides on the organizers' background artwork, live schedule, game
servers, tournament and stream data, and a Django admin for the people
running the event. Runs on the venue network.

## Quickstart

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py loadcontent
uv run python manage.py createsuperuser
uv run python manage.py spectacular --file frontend/openapi.yaml --validate
(cd frontend && pnpm install && pnpm openapi)
uv run python manage.py runserver        # admin and API on :8000
(cd frontend && pnpm dev)                # the display on :5173, proxying the backend
```

Open <http://localhost:5173/> for the screen and <http://localhost:5173/admin/>
to manage it. In the admin you set the event facts and the Wi-Fi, pick the
phase, edit slides and the schedule, publish announcements from templates,
upload a different background SVG, add screens, and configure the
Projectile, Bracket and Streams connections (URL, credentials, timeouts).
Nothing else needs editing during an event.

## Containers

One image per component, each holding only what that component needs:

- `docker/backend.Dockerfile`: the Django backend (admin, API, integrations).
- `docker/frontend.Dockerfile`: the React display, served by a rootless nginx
  that also proxies the backend paths, so kiosks talk to one origin.
- `docker/minio.Dockerfile`: MinIO, built from its last community release,
  holding Django's static files and the uploaded background.

Copy `.env.example` to `.env`, fill it in, then `docker compose up -d` for
the published images with Postgres, or
`docker compose -f compose.local.yaml up --build` to build everything from
this checkout against SQLite. The display is then at <http://localhost:8080/>.

## What is here

- `src/`: the Django backend (`config` settings, `signage` app with models, admin, API, integrations).
- `frontend/`: the React 19 + TypeScript + Tailwind CSS v4 display, built by Vite.
- `docker/`, `compose.yaml`, `compose.local.yaml`: the images and the stacks.
- `content/`: event facts, schedule, games, slides and announcement templates as YAML.
- `assets/background.svg`: the 1920x1080 background.
- `scripts/render_content.py`: lints the YAML; `scripts/screenshots.py`: checks every slide against the safe area.
- [`AGENTS.md`](AGENTS.md): the guide for humans and AI agents: decisions, invariants, conventions, checks.

## Editing the copy

```bash
# edit content/*.yaml, then
python3 scripts/render_content.py --check
```

The script needs PyYAML and fails on missing translations, too many bullets
or banned typography. Without `--check` it also renders a Markdown preview
to the git-ignored `docs/content.md`.

## Stack

Django 6 with django-solo, Django REST framework, drf-spectacular and
django-storages on the backend; React 19, TypeScript, Vite, Tailwind CSS v4
and daisyUI with TanStack Query, Embla Carousel and friends on the display;
MinIO for the static files. Versions are pinned in `pyproject.toml`,
`uv.lock`, `frontend/package.json` and the Dockerfiles.

## License

GPL-3.0, see [`LICENSE`](LICENSE).
