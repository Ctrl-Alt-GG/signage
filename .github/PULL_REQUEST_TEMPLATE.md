<!--
Thanks for contributing to the Ctrl-Alt-GG Signage.
Keep this short. If a section does not apply, delete it.
-->

## What changed

<!-- One or two sentences. What does this PR do, and why? -->

## Milestone

<!-- Which docs/spec.md milestone (M0 to M6) or "content" / "docs". -->

## Scope

- [ ] Content (`content/*.yaml`, regenerated `docs/content.md`)
- [ ] Application code (`src/`)
- [ ] Templates, CSS, player (`src/signage/templates`, `static_src`, `static`)
- [ ] Integrations (`src/signage/integrations`)
- [ ] Configuration (`pyproject.toml`, settings, Compose, Dockerfile, workflows)
- [ ] Docs and agent files (`docs/`, `AGENTS.md`, `.github/`)

## Checks

- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `python3 scripts/render_content.py --check` passes
- [ ] `uv run python manage.py check` and `makemigrations --check` pass
- [ ] `uv run pytest` passes
- [ ] `scripts/screenshots.py` passes and screenshots are regenerated if templates or CSS changed
- [ ] No generated artefacts committed (compiled CSS, `staticfiles/`, `db.sqlite3`, caches)
- [ ] Every string on screen exists in `hu` and `en`; chrome strings are translated
- [ ] No em dashes, en dashes, ellipsis characters or curly quotes in the diff
- [ ] The milestone's acceptance list in `docs/spec.md` section 15 is satisfied
- [ ] Agent-facing docs updated if behaviour or conventions changed

## Screenshots / notes

<!-- Optional. Required for layout, template or CSS changes. -->
