# Copilot instructions

The canonical guide for this repo is [`AGENTS.md`](../AGENTS.md). Read it
first; this file only lists always-true invariants so Copilot Chat never
breaks them.

## Stack

Django backend, React 19 + TypeScript + Tailwind CSS v4 display, MinIO for
static files, one container image per component. `uv`, `ruff`, `pnpm`. Do
not hard-code versions; read them from `pyproject.toml`, `uv.lock`,
`.python-version`, `frontend/package.json`, `frontend/.nvmrc` and
`docker/*.Dockerfile`.

## Non-negotiables

- The decisions in `AGENTS.md` section 3 are settled. Build what it says.
- All on-screen content stays inside the content-safe area of
  `assets/background.svg`: x 96 to 1824, y 204 to 768 in the 1920x1080
  stage. Never edit the SVG.
- Copy lives in `content/*.yaml` and is linted by
  `scripts/render_content.py --check`.
- Every slide string exists in Hungarian (`hu`) and English (`en`) and
  both are shown, Hungarian first and larger. Hungarian is informal "te".
- Prose must never contain em dashes, en dashes, ellipsis characters,
  curly quotes, non-breaking spaces or emoji. Hyphens for ranges, three
  periods for an ellipsis, straight quotes.
- Tailwind v4 syntax only (`@import "tailwindcss"`, `@theme`, `@source`).
  One source stylesheet; never commit compiled CSS.
- The frontend talks only to the backend. Upstream systems are the
  backend's business, configured in the Django admin.
- Generated files are git-ignored and never committed: the OpenAPI schema,
  the TypeScript API types, build output, screenshots, `docs/`.
- No alpine image variants. Each image contains only what its component
  needs to run.
- The room never sees an error: live slides fall back to last-good data,
  then to their `empty` text.
- Nothing is fetched from the public internet by the display: fonts, icons
  and QR codes are bundled or generated.
