# The display: the React app built by Vite and served by a rootless nginx that also proxies
# the backend paths, so a kiosk only ever talks to one origin.

# Stage 1: the OpenAPI schema from the backend serializers. The TypeScript types the display
# compiles against are generated from it, so they always match the API the image will talk to.
FROM python:3.14-slim-trixie AS schema
ENV DJANGO_SETTINGS_MODULE=config.settings.production \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /bin/uv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev
COPY manage.py ./
COPY src ./src
RUN DJANGO_SECRET_KEY=build DJANGO_ALLOWED_HOSTS=localhost \
    uv run --frozen --no-dev python manage.py spectacular --file /openapi.yaml --validate

# Stage 2: the Vite build.
FROM node:24-trixie-slim AS build
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
WORKDIR /build
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
COPY --from=schema /openapi.yaml ./openapi.yaml
RUN pnpm openapi && pnpm build

# Stage 3: rootless nginx (Debian based) with the static build and the proxy configuration.
FROM nginxinc/nginx-unprivileged:1.30-trixie

LABEL org.opencontainers.image.description="Ctrl-Alt-GG Signage display: the React screen served by nginx."

# The entrypoint renders /etc/nginx/templates into conf.d; only BACKEND_URL is substituted.
ENV BACKEND_URL=http://web:8000 \
    NGINX_ENVSUBST_FILTER="^BACKEND_URL\$"

COPY docker/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /build/dist /usr/share/nginx/html

EXPOSE 8080
