# Ctrl-Alt-GG Signage

Digital signage for the [Ctrl-Alt-GG](https://www.ctrl-alt-gg.hu) LAN party:
bilingual slides on the organizers' background artwork, live schedule, game
servers, tournament and stream data, and a Django admin for the people
running the event. Runs on the venue network.

This repository currently contains the specification, the design rules and
the content. The application itself is to be built by following
[`AGENTS.md`](AGENTS.md) and [`docs/spec.md`](docs/spec.md).

## What is here

- [`AGENTS.md`](AGENTS.md): entry point for humans and AI agents, conventions, reading order.
- [`docs/spec.md`](docs/spec.md): Django and Tailwind CSS v4 build specification with milestones.
- [`docs/design.md`](docs/design.md): the background, the content-safe area, tokens, layouts.
- [`docs/integrations.md`](docs/integrations.md): the sibling systems and their APIs.
- [`docs/content.md`](docs/content.md): the text on the screens, generated from `content/`.
- [`content/`](content/): event facts, schedule, games, slides and announcement templates as YAML.
- [`assets/background.svg`](assets/background.svg): the 1920x1080 background.
- [`scripts/render_content.py`](scripts/render_content.py): lints the YAML and renders `docs/content.md`.

## Editing the copy

```bash
# edit content/*.yaml, then
python3 scripts/render_content.py
```

The script needs PyYAML and fails on missing translations, too many bullets
or banned typography. Commit the regenerated `docs/content.md` with the YAML.

## Stack

Python, Django, Tailwind CSS v4, served from a non-root container on the
venue network. Versions are pinned in the project files once the
application exists; see `docs/spec.md` section 1 for the decisions.

## License

GPL-3.0, see [`LICENSE`](LICENSE).
