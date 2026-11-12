# The Django backend: admin, JSON API, integrations. Nothing else runs here: the display and
# the admin's static files are the frontend image.
FROM python:3.14-slim-trixie

LABEL org.opencontainers.image.description="Ctrl-Alt-GG Signage backend: Django admin and JSON API."

ENV DJANGO_SETTINGS_MODULE=config.settings.production \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEDIA_ROOT=/app/data/media

WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

# Resolve the locked dependencies into the system interpreter, then drop uv again.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /bin/uv
COPY pyproject.toml uv.lock README.md ./
RUN uv export --frozen --no-dev --no-emit-project --output-file /tmp/requirements.txt \
    && uv pip install --system --require-hashes --no-cache \
        --python /usr/local/bin/python --requirement /tmp/requirements.txt \
    && rm -f /bin/uv /tmp/requirements.txt

# The code stays owned by root, so the process that serves requests cannot rewrite it.
# What it does write goes into volumes: the uploaded background under data/media, and the
# SQLite database of the local stack under data/db. A named volume takes over the owner
# of the directory it is mounted on, so both exist here and belong to the app user.
COPY manage.py ./
COPY src ./src
COPY assets ./assets
COPY content ./content
RUN mkdir -p /app/data/media /app/data/db && chown -R 10001:10001 /app/data
VOLUME ["/app/data/media"]

USER 10001:10001
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--config", "python:config.gunicorn"]
