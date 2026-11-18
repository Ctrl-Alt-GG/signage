"""What several test modules use to point an integration at a mocked upstream."""

from signage.models import Integration

BASIC = {"auth_type": Integration.Auth.BASIC, "username": "u", "password": "p"}
BRACKET = "https://bracket.example/api"


def configure(kind: str, url: str, **values) -> Integration:
    row = Integration.objects.get(kind=kind)
    row.enabled = True
    row.base_url = url
    for name, value in values.items():
        setattr(row, name, value)
    row.full_clean()
    row.save()
    return row


class FakeClock:
    """A monotonic clock that only moves when a test moves it."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
