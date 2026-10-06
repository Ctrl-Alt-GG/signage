# The Django backend: admin, JSON API, integrations. Nothing else runs here: the display is
# the frontend image, static files and uploads live in the storage bucket.
FROM python:3.14-slim-trixie

LABEL org.opencontainers.image.description="Ctrl-Alt-GG Signage backend: Django admin and JSON API."

ENV DJANGO_SETTINGS_MODULE=config.settings.production \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

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

COPY --chown=10001:10001 manage.py ./
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 assets ./assets
COPY --chown=10001:10001 content ./content

USER 10001:10001
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--config", "python:config.gunicorn"]
