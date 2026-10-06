# AGENTS.md: Ctrl-Alt-GG Signage

> Canonical guide for AI coding agents (GitHub Copilot, Cursor, Codex, Claude
> and friends) and for humans working on this repository. Read this first,
> then the documents it points to, in the order given.

## 1. What this repo is

The digital signage for the Ctrl-Alt-GG LAN party: a Django application
that rotates bilingual (Hungarian first, English second) slides on the
organizers' background artwork, mixes in live data from the other
Ctrl-Alt-GG systems (schedule, game servers, tournament, streams), and gives
organizers a Django admin to steer it during the event. It runs on the
venue network only.

The repository currently holds the specification and the content. The
application has not been built yet; building it is the job described in
`docs/spec.md`.

## 2. Reading order

1. `docs/spec.md`: decisions, data model, contracts, milestones, done criteria.
2. `docs/design.md`: the background anatomy, the content-safe area, tokens,
   type scale, the eleven layouts, motion and readability rules, QA.
3. `docs/integrations.md`: the sibling systems, their endpoints and JSON
   shapes, environment variables, inherited conventions.
4. `docs/content.md`: the copy on the screens, rendered from `content/*.yaml`.
5. `content/*.yaml`: the source of truth for the copy, the schedule, the
   games, the event facts and the announcement templates.

If a document and this file disagree, the document wins for its own topic
and this file needs a fix in the same PR.

## 3. Source of truth

| Fact | Lives in |
|---|---|
| What to build, in which order, and when it is done | `docs/spec.md` |
| Pixel values, colours, fonts, layout rules | `docs/design.md` |
| Upstream URLs, JSON shapes, polling rules | `docs/integrations.md` |
| Slide copy | `content/slides.yaml` (rendered to `docs/content.md`) |
| Schedule rows | `content/schedule.yaml` |
| Games, colours, Projectile aliases | `content/games.yaml` |
| Venue, Wi-Fi, links, organizers, phases | `content/event.yaml` |
| Announcement templates | `content/announcements.yaml` |
| The background artwork | `assets/background.svg` (never edited) |
| Tool versions, once the app exists | `pyproject.toml`, `uv.lock`, `.python-version`, `docker/web.Dockerfile` |

Do not repeat versions or URLs in prose; link to the file that pins them.

## 4. How to work

- One milestone per pull request, in the order `docs/spec.md` section 15
  gives. Each PR's checklist is that milestone's acceptance list plus the
  definition of done in section 16.
- Decisions in `docs/spec.md` section 1 are settled. If one cannot be
  honoured, say why in the PR description and choose the nearest
  alternative; do not reopen the discussion in code comments.
- Content changes go through the YAML files, then
  `python3 scripts/render_content.py` to regenerate `docs/content.md`.
  Never edit `docs/content.md` by hand; CI runs the script with `--check`.
- Keep the copy honest to its sources. The slides condense pages from the
  homepage and Care; when those pages change, change the YAML, not the
  other way round. Anything that only an organizer knows (Wi-Fi SSID,
  assembly point, dates) stays `CHANGE-ME` in the seed and is set in the
  admin; the app refuses to show a slide with an unresolved value.
- Prefer boring code: Django templates, one JavaScript file, stock admin.
  No new framework, bundler, or service without a line in
  `docs/spec.md` section 1 explaining why.

## 5. Conventions

- Python 3.14, Django 6, `uv`, `ruff` (line length 100, rules
  `E F I N UP B SIM DJ RUF`), `src/` layout, settings split
  `base/development/production/local`, mirrored from `Ctrl-Alt-GG/streams`.
- Tailwind CSS v4 syntax only: `@import "tailwindcss"`, `@theme`,
  `@source`, `@custom-variant`. One source file,
  `src/signage/static_src/app.css`. Compiled CSS is generated and ignored.
- Bilingual content is data: `_hu` and `_en` columns, Hungarian required.
  UI chrome strings go through `gettext` with Hungarian translations in
  `src/locale/hu`.
- Hungarian is written natively, informal "te", second person, present
  tense. English is idiomatically independent, not a calque.
- Prose rules from the homepage apply to copy, docs, comments and commit
  messages: no em dashes, no en dashes, no ellipsis character, no curly
  quotes, no non-breaking spaces, no emoji in text, no filler
  superlatives. Hyphen for ranges (`10-15 perc`), three periods for an
  ellipsis, straight quotes.
- Comments state what the code cannot. No narration of the next line.
- Commit messages: imperative subject under 72 characters, a body that
  says why. No model names or tool advertisements in commits.

Sweep before committing:

```bash
git diff --name-only main \
  | grep -v 'scripts/render_content.py' \
  | xargs -r env LC_ALL=C.UTF-8 grep -HnP '[\x{2013}\x{2014}\x{2026}\x{2018}\x{2019}\x{201C}\x{201D}\x{00A0}]'
```

The sweep must print nothing. `scripts/render_content.py` is excluded
because it lists the banned glyphs in order to reject them. Use a UTF-8
locale: under `LC_ALL=C` a byte-wise bracket match flags accented letters
such as `Ó` and `Ü` by mistake.

## 6. Running the project (once M0 exists)

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py loadcontent
uv run python manage.py tailwind build      # or `tailwind watch` while developing
uv run python manage.py runserver
# open http://127.0.0.1:8000/display/main/ and http://127.0.0.1:8000/admin/
```

Before the first milestone lands, the only runnable thing is
`python3 scripts/render_content.py`, which needs PyYAML.

## 7. Do-not-touch list

- `assets/background.svg`: the organizers' artwork, stored verbatim.
- `docs/content.md`: generated.
- `src/signage/static/signage/css/**` and any other compiled CSS:
  generated.
- `docs/screenshots/**`: generated by `scripts/screenshots.py`; regenerate,
  never hand-edit.
- `.github/workflows/**` unless the workflow is the subject of the change.
- Content of `LICENSE` (GPL-3.0).

## 8. Definition of done

A change is done when the checklist in `docs/spec.md` section 16 is
satisfied and the milestone's acceptance list passes. "It renders on my
machine" is not done; the screenshot script and the safe-area test are.

## 9. Where the other agent files fit

- `.github/copilot-instructions.md`: thin always-loaded pointer to this
  document with the invariants Copilot Chat must never break.
- `.github/PULL_REQUEST_TEMPLATE.md`: the PR checklist.
- Path-scoped `.github/instructions/*.instructions.md` files may be added
  per milestone (templates, CSS, integrations) following the pattern used
  by `Ctrl-Alt-GG/homepage`.
