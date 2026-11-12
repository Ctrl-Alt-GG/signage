import pytest

from signage.content.lint import LintError
from signage.content.safe_yaml import load_yaml


def test_plain_content_loads():
    assert load_yaml('slides:\n  - title: "Cím"\n    enabled: true\n') == {
        "slides": [{"title": "Cím", "enabled": True}]
    }


def test_alias_bomb_is_rejected_before_mapping_construction(monkeypatch):
    from signage.content.safe_yaml import ContentLoader

    def must_not_construct(*args, **kwargs):
        pytest.fail("the alias document reached mapping construction")

    monkeypatch.setattr(ContentLoader, "construct_mapping", must_not_construct)
    lines = ["seed: &n0 {value: x}"]
    for i in range(1, 24):
        lines.append(f"n{i}: &n{i} {{<<: [*n{i - 1}, *n{i - 1}]}}")
    with pytest.raises(LintError, match="aliases are not supported"):
        load_yaml("\n".join(lines))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("row: {<<: {key: value}}", "merge keys are not supported"),
        ("[" * 51 + "x" + "]" * 51, "nesting is limited"),
        ("- x\n" * 20_001, "limited to 20000 values"),
    ],
)
def test_expensive_yaml_shapes_are_bounded(text, message):
    with pytest.raises(LintError, match=message):
        load_yaml(text)
