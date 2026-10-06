# Ctrl-Alt-GG Signage

Digital signage for the [Ctrl-Alt-GG](https://www.ctrl-alt-gg.hu) LAN party:
bilingual slides on the organizers' background artwork, live schedule, game
servers, tournament and stream data, and a Django admin for the people
running the event. Runs on the venue network.

## Quickstart

```bash
uv sync
(cd frontend && pnpm install && pnpm build)
uv run python manage.py migrate
uv run python manage.py loadcontent
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Open <http://127.0.0.1:8000/display/main/> for the screen and
<http://127.0.0.1:8000/admin/> to manage it. In the admin you set the event
facts and the Wi-Fi, pick the phase, edit slides and the schedule, publish
announcements from templates, upload a different background SVG, add
screens, and configure the Projectile, Bracket and Streams connections
(URL, credentials, timeouts). Nothing else needs editing during an event.

With Docker: copy `.env.example` to `.env`, fill it in, then
`docker compose up -d` (Postgres plus the published image), or
`docker compose -f compose.local.yaml up --build` for a local SQLite build.

## What is here

- `src/`: the Django backend (`config` settings, `signage` app with models, admin, API, integrations).
- `frontend/`: the React 19 + TypeScript + Tailwind CSS v4 display, built by Vite and served by Django.
- `docker/`, `compose.yaml`, `compose.local.yaml`: the container image and stacks.

- [`AGENTS.md`](AGENTS.md): entry point for humans and AI agents, conventions, reading order.
- [`docs/spec.md`](docs/spec.md): Django and Tailwind CSS v4 build specification with milestones.
- [`docs/design.md`](docs/design.md): the background, the content-safe area, tokens, layouts.
- [`docs/integrations.md`](docs/integrations.md): the sibling systems and their APIs.
- [`docs/content.md`](docs/content.md): the text on the screens, generated from `content/`.
- [`content/`](content/): event facts, schedule, games, slides and announcement templates as YAML.
- [`assets/background.svg`](assets/background.svg): the 1920x1080 background.
- [`scripts/render_content.py`](scripts/render_content.py): lints the YAML and renders `docs/content.md`.

## Editing the copy

```bash
# edit content/*.yaml, then
python3 scripts/render_content.py
```

The script needs PyYAML and fails on missing translations, too many bullets
or banned typography. Commit the regenerated `docs/content.md` with the YAML.

## Stack

Django 6 with django-solo, Django REST framework, drf-spectacular,
django-vite and WhiteNoise on the backend; React 19, TypeScript, Vite,
Tailwind CSS v4 and daisyUI with TanStack Query, Embla Carousel and friends
on the display. Versions are pinned in `pyproject.toml`, `uv.lock` and
`frontend/package.json`; `docs/spec.md` section 1 lists every library and
why it is there.

## License

GPL-3.0, see [`LICENSE`](LICENSE).
