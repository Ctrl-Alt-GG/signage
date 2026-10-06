<!--
Thanks for contributing to the Ctrl-Alt-GG Signage.
Keep this short. If a section does not apply, delete it.
-->

## What changed

<!-- One or two sentences. What does this PR do, and why? -->

## Scope

- [ ] Content (`content/*.yaml`)
- [ ] Backend (`src/`)
- [ ] Display (`frontend/`)
- [ ] Integrations (`src/signage/integrations`)
- [ ] Containers and configuration (`docker/`, Compose, `.env.example`, settings, workflows)
- [ ] Agent files (`AGENTS.md`, `.github/`)

## Checks

- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run pytest` passes (includes Django checks, migrations, content lint, schema validity)
- [ ] `manage.py spectacular`, then `pnpm openapi && pnpm typecheck && pnpm test && pnpm build` pass
- [ ] `scripts/screenshots.py` passes if layouts or styles changed
- [ ] No generated files committed (schema, API types, build output, screenshots, `docs/`, caches)
- [ ] Every string on screen exists in `hu` and `en`
- [ ] No em dashes, en dashes, ellipsis characters or curly quotes in the diff
- [ ] `AGENTS.md` updated if behaviour or conventions changed

## Screenshots / notes

<!-- Optional. Required for layout or style changes. -->
