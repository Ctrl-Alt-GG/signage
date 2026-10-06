import copy

import pytest

from signage.content import lint

PHASES = ["setup", "play"]
GOOD = {
    "slides": [
        {
            "id": "a",
            "layout": "list",
            "phases": ["play"],
            "title": {"hu": "Cím", "en": "Title"},
            "items": [{"hu": "x", "en": "y"}],
        }
    ]
}


def test_good_slides_pass():
    lint.lint_slides(GOOD, PHASES)


def test_missing_english_fails():
    bad = copy.deepcopy(GOOD)
    bad["slides"][0]["title"] = {"hu": "Cím"}
    with pytest.raises(lint.LintError, match="missing or empty 'en'"):
        lint.lint_slides(bad, PHASES)


def test_seventh_item_fails():
    bad = copy.deepcopy(GOOD)
    bad["slides"][0]["items"] = [{"hu": "x", "en": "y"}] * 7
    with pytest.raises(lint.LintError, match="at most 6"):
        lint.lint_slides(bad, PHASES)


def test_split_needs_two_columns():
    bad = copy.deepcopy(GOOD)
    bad["slides"][0]["layout"] = "split"
    bad["slides"][0]["columns"] = [{"title": {"hu": "a", "en": "b"}, "items": []}]
    with pytest.raises(lint.LintError, match="two columns"):
        lint.lint_slides(bad, PHASES)


def test_unknown_phase_fails():
    bad = copy.deepcopy(GOOD)
    bad["slides"][0]["phases"] = ["afterparty"]
    with pytest.raises(lint.LintError, match="unknown phases"):
        lint.lint_slides(bad, PHASES)


def test_banned_glyph_fails():
    with pytest.raises(lint.LintError, match="em dash"):
        lint.lint_text("hello " + chr(0x2014) + " world", "x.yaml")
