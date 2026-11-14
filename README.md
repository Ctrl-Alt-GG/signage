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
The Overview, linked from the admin's front page, shows the phase, every
screen with a live preview, and the state of each connection. Nothing else
needs editing during an event. A screen turned off in the admin shows only
the background.

## Upstream systems

Give each connection the system's public HTTPS address as its API root, for
example `https://streams.ctrl-alt-gg.hu/api/v1` for Streams. That works with
the security settings of all of them. The client follows no redirects, as it
carries the upstream's credentials; when a server redirects, the Overview
names the address to use instead.

Bracket needs no authentication: a tournament whose Details page is on is
public. A Bracket login token expires (after 12 hours by default), so don't
rely on one.

To reach Streams over the Docker network instead, both stacks have to join one
network, and Streams has to answer there without TLS:

1. On the host, `docker network create streams-internal`. Attach Streams' web
   service to it with the alias `streams-web`, as the Streams README
   describes, and attach this stack's `web` service to it in a
   `compose.override.yaml`:

   ```yaml
   services:
     web:
       networks: [default, streams-internal]
   networks:
     streams-internal:
       external: true
   ```

2. In Streams' `.env`, add `streams-web` to `DJANGO_ALLOWED_HOSTS` and set
   `DJANGO_SECURE_REDIRECT_EXEMPT=^api/v1/,^streams/[^/]+/thumbnail/`.
3. Set the API root here to `http://streams-web:8000/api/v1`.

The requests and the thumbnails then travel unencrypted: any container on
`streams-internal` can read and change them. The public address avoids that.

## Containers

One image per component, each holding only what that component needs:

- `docker/backend.Dockerfile`: the Django backend (admin, API, integrations).
- `docker/frontend.Dockerfile`: the React display, served by a rootless nginx
  that also proxies the backend paths and serves Django's collected static
  files, so kiosks talk to one origin.

Background uploads live in the backend's persistent `media` volume and are
served through the API. Back up that volume alongside the database. Existing
S3 background uploads must be copied to `media/background/` before switching
to this stack; keep their existing relative file names from Display settings.
Static files are included in the frontend image and need no storage service.

Copy `.env.example` to `.env`, fill it in, then `docker compose up -d` for
the published images with Postgres, or
`docker compose -f compose.local.yaml up --build` to build everything from
this checkout against SQLite. The display is then at <http://localhost:8080/>.
Compose passes `.env` to the backend containers; Postgres receives only its
own `POSTGRES_*` variables.

The production admin requires HTTPS at the host reverse proxy, which must
set `X-Forwarded-Proto`. The local stack allows plain HTTP only on localhost.
The proxy reaches the published port through the gateway of the compose
network, which has the fixed subnet `172.31.242.0/24`. nginx trusts
`X-Forwarded-For` and `X-Forwarded-Proto` from that gateway, `TRUSTED_PROXY`
(`172.31.242.1` by default), and from nobody else, so its login limit counts
each client of the proxy on its own. If the subnet is taken on the host,
change it in `compose.yaml` and set `TRUSTED_PROXY` to the new gateway. The
proxy must pass the client address as the last `X-Forwarded-For` entry, as
nginx's `$proxy_add_x_forwarded_for` does.

The admin sends HSTS (`DJANGO_SECURE_HSTS_SECONDS`, a year by default), so a
browser that has seen it over HTTPS never asks its host name, or one below
it, over plain HTTP again. Screens that load the display over plain HTTP use
the IP address or another host name.

The admin and the API are served with a Content-Security-Policy that allows
nothing from elsewhere and no inline script or style; the display's own policy
is in `docker/nginx/default.conf.template`.

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
filesystem uploads on the backend; React 19, TypeScript, Vite, Tailwind CSS v4
and daisyUI with TanStack Query, Embla Carousel and friends on the display;
nginx for the static files. Versions are pinned in `pyproject.toml`,
`uv.lock`, `frontend/package.json` and the Dockerfiles.

## License

GPL-3.0, see [`LICENSE`](LICENSE).
