"""Bounded YAML for content files. Imports need simple mappings and lists, not aliases
or merge keys, which can multiply a tiny upload into a very large structure."""

from __future__ import annotations

from typing import Any

import yaml

from signage.content.lint import LintError

MAX_DEPTH = 50
MAX_NODES = 20_000


class ContentLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self.depth = 0
        self.nodes = 0

    def compose_node(self, parent, index):
        event = self.peek_event()
        if self.check_event(yaml.AliasEvent):
            raise yaml.composer.ComposerError(
                None,
                None,
                "YAML aliases are not supported; write each value directly",
                event.start_mark,
            )
        if self.depth >= MAX_DEPTH:
            raise yaml.composer.ComposerError(
                None, None, f"YAML nesting is limited to {MAX_DEPTH} levels", event.start_mark
            )
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise yaml.composer.ComposerError(
                None, None, f"YAML is limited to {MAX_NODES} values", event.start_mark
            )
        self.depth += 1
        try:
            return super().compose_node(parent, index)
        finally:
            self.depth -= 1

    def construct_mapping(self, node, deep=False):
        for key, _ in node.value:
            if key.tag == "tag:yaml.org,2002:merge":
                raise yaml.constructor.ConstructorError(
                    None,
                    None,
                    "YAML merge keys are not supported; write each field directly",
                    key.start_mark,
                )
        return super().construct_mapping(node, deep=deep)


def load_yaml(text: str) -> Any:
    try:
        return yaml.load(text, Loader=ContentLoader)
    except yaml.YAMLError as error:
        raise LintError(str(error)) from error
