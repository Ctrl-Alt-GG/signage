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


SCHEDULE = {
    "entries": [
        {"key": "a", "time": "22:00", "type": "play", "title": {"hu": "Este", "en": "Evening"}},
        {
            "key": "b",
            "time": "01:00",
            "day_offset": 1,
            "type": "play",
            "title": {"hu": "Éjjel", "en": "Night"},
        },
    ]
}


def test_good_schedule_passes():
    lint.lint_schedule(SCHEDULE, [])
    single_digit = copy.deepcopy(SCHEDULE)
    single_digit["entries"][0]["time"] = "9:30"
    single_digit["entries"][1]["day_offset"] = 0
    single_digit["entries"][1]["time"] = "10:00"
    lint.lint_schedule(single_digit, [])


def test_an_unquoted_time_is_explained():
    """YAML reads 10:00 without quotes as the number 600."""
    bad = copy.deepcopy(SCHEDULE)
    bad["entries"][0]["time"] = 600
    with pytest.raises(lint.LintError, match="quoted time"):
        lint.lint_schedule(bad, [])
    bad["entries"][0]["time"] = "25:00"
    with pytest.raises(lint.LintError, match="quoted time"):
        lint.lint_schedule(bad, [])
    event = {
        "event": {},
        "venue": {},
        "wifi": {},
        "links": {},
        "phases": [{"key": "play", "starts": 930, "hu": "Játék", "en": "Play"}],
    }
    with pytest.raises(lint.LintError, match="quoted time"):
        lint.lint_event(event)


def test_a_slot_after_midnight_needs_its_day():
    """Left on day 0, it would sort before the event and never become the current slot."""
    bad = copy.deepcopy(SCHEDULE)
    del bad["entries"][1]["day_offset"]
    with pytest.raises(lint.LintError, match="after midnight needs day_offset: 1"):
        lint.lint_schedule(bad, [])


def test_unknown_placeholder_fails():
    bad = copy.deepcopy(GOOD)
    bad["slides"][0]["items"] = [{"hu": "Hálózat: {wifi_name}", "en": "Network: {wifi_ssid}"}]
    with pytest.raises(lint.LintError, match=r"unknown placeholder \{wifi_name\}"):
        lint.lint_slides(bad, PHASES)
    # Other braces are text, and a known name is fine.
    good = copy.deepcopy(GOOD)
    good["slides"][0]["items"] = [{"hu": "{wifi_ssid} { }", "en": "{wifi_ssid} {Nope}"}]
    lint.lint_slides(good, PHASES)


def test_a_file_of_another_shape_is_a_lint_error():
    for document in ({"slides": "not a list"}, {"slides": ["not a mapping"]}):
        with pytest.raises(lint.LintError, match="expected a"):
            lint.lint_slides(document, PHASES)
    with pytest.raises(lint.LintError, match="expected a"):
        lint.lint_schedule({"entries": {"key": "a"}}, [])
