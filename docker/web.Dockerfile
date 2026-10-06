# Stage 1: build the React display with Vite.
FROM node:22-slim AS frontend
WORKDIR /build
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# Stage 2: the Django application, non-root, serving the built assets with WhiteNoise.
FROM python:3.14-slim

LABEL org.opencontainers.image.description="Ctrl-Alt-GG Signage: Django backend and React display for the LAN party screens."

ENV DJANGO_SETTINGS_MODULE=config.settings.production \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1

WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && apt-get update \
    && apt-get install --yes --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir uv==0.11.32

COPY pyproject.toml uv.lock README.md ./
RUN uv export --frozen --no-dev --no-emit-project --output-file /tmp/requirements.txt \
    && uv pip install --system --require-hashes --no-cache \
        --python /usr/local/bin/python --requirement /tmp/requirements.txt \
    && python -m pip uninstall --yes uv \
    && rm -rf /root/.cache /tmp/requirements.txt

COPY --chown=10001:10001 manage.py ./
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 assets ./assets
COPY --chown=10001:10001 content ./content
COPY --chown=10001:10001 --from=frontend /build/dist ./frontend/dist

RUN mkdir -p /app/data/staticfiles /app/data/media && chown -R 10001:10001 /app/data \
    && DJANGO_SECRET_KEY=build DJANGO_ALLOWED_HOSTS=localhost \
       python manage.py collectstatic --noinput

USER 10001:10001
EXPOSE 8000
VOLUME ["/app/data/media"]

CMD ["gunicorn", "config.wsgi:application", "--config", "python:config.gunicorn"]
