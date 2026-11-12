import pytest

from signage.rendering.placeholders import UnresolvedPlaceholderError, resolve


def test_placeholders_resolve(event):
    hu, en = event.placeholder_values("hu"), event.placeholder_values("en")
    assert resolve("SSID {wifi_ssid}", hu) == "SSID CtrlAltGG"
    assert resolve("{starts_at_time}", hu) == "15:30"
    assert resolve("{starts_at_date}", hu) == "2026. 10. 03."
    assert resolve("{starts_at_date}", en) == "3 October 2026"


def test_change_me_is_rejected(event):
    event.wifi_ssid = "CHANGE-ME"
    with pytest.raises(UnresolvedPlaceholderError) as error:
        resolve("{wifi_ssid}", event.placeholder_values("hu"))
    assert error.value.name == "wifi_ssid"
    with pytest.raises(UnresolvedPlaceholderError):
        resolve("Jelszó: CHANGE-ME", event.placeholder_values("hu"))


def test_unknown_placeholder_is_rejected(event):
    with pytest.raises(UnresolvedPlaceholderError) as error:
        resolve("{nope}", event.placeholder_values("hu"))
    assert error.value.name == "nope"


def test_braces_in_a_value_are_shown_as_they_are(event):
    """A Wi-Fi password may hold braces. They are part of the password, not a placeholder
    that was left unfilled, and the slide that shows it stays on the screens."""
    event.wifi_password = "p{ss}w0rd{"
    assert resolve("Jelszó: {wifi_password}", event.placeholder_values("hu")) == (
        "Jelszó: p{ss}w0rd{"
    )


def test_braces_that_are_not_a_placeholder_are_text(event):
    values = event.placeholder_values("hu")
    for text in ("{ }", "a } b { c", "{Nagy Betű}", "{két szó}", "{}", "{0}"):
        assert resolve(text, values) == text
