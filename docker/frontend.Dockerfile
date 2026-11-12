# The display: the React app built by Vite and served by a rootless nginx that also proxies
# the backend paths and serves the admin's static files, so a kiosk or an organizer only
# ever talks to one origin.

# Stage 1: what the backend contributes to this image. The OpenAPI schema from its
# serializers, which the display's TypeScript types are generated from, so they always
# match the API the image will talk to. And the static files of the Django admin.
FROM python:3.14-slim-trixie AS backend
ENV DJANGO_SETTINGS_MODULE=config.settings.production \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1 \
    STATIC_ROOT=/static
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /bin/uv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev
COPY manage.py ./
COPY src ./src
# Django's system checks open a database connection (JSONField support), so the commands
# get an in-memory SQLite database; neither of them needs data.
RUN DJANGO_SECRET_KEY=build DJANGO_ALLOWED_HOSTS=localhost DATABASE_URL=sqlite://:memory: \
    uv run --frozen --no-dev python manage.py spectacular --file /openapi.yaml --validate \
    && DJANGO_SECRET_KEY=build DJANGO_ALLOWED_HOSTS=localhost DATABASE_URL=sqlite://:memory: \
    uv run --frozen --no-dev python manage.py collectstatic --noinput

# Stage 2: the Vite build.
FROM node:24-trixie-slim AS build
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
WORKDIR /build
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
COPY --from=backend /openapi.yaml ./openapi.yaml
RUN pnpm openapi && pnpm build

# Stage 3: rootless nginx (Debian based) with the static build and the proxy configuration.
FROM nginxinc/nginx-unprivileged:1.30-trixie

LABEL org.opencontainers.image.description="Ctrl-Alt-GG Signage display: the React screen served by nginx."

# The entrypoint renders /etc/nginx/templates into conf.d; only BACKEND_URL is substituted.
ENV BACKEND_URL=http://web:8000 \
    NGINX_ENVSUBST_FILTER="^BACKEND_URL\$"

COPY docker/nginx/ /etc/nginx/templates/
COPY --from=build /build/dist /usr/share/nginx/html
COPY --from=backend /static /usr/share/nginx/static

EXPOSE 8080
