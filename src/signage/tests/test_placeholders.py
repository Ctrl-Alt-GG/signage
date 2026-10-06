import pytest

from signage.rendering.placeholders import UnresolvedPlaceholderError, resolve


def test_placeholders_resolve(event):
    assert resolve("SSID {wifi_ssid}", event, "hu") == "SSID CtrlAltGG"
    assert resolve("{starts_at_time}", event, "hu") == "15:30"
    assert resolve("{starts_at_date}", event, "hu") == "2026. 10. 03."
    assert resolve("{starts_at_date}", event, "en") == "3 October 2026"


def test_change_me_is_rejected(event):
    event.wifi_ssid = "CHANGE-ME"
    with pytest.raises(UnresolvedPlaceholderError) as error:
        resolve("{wifi_ssid}", event, "hu")
    assert error.value.name == "wifi_ssid"


def test_unknown_placeholder_is_rejected(event):
    with pytest.raises(UnresolvedPlaceholderError):
        resolve("{nope}", event, "hu")
