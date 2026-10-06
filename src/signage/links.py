from django.conf import settings


def display_url(slug: str) -> str:
    """Browser URL of a screen on the display frontend.

    The frontend is a separate container (nginx) that proxies the admin, so by default the
    link is relative to the admin's own origin; DISPLAY_BASE_URL makes it absolute when the
    admin is reached directly on the backend.
    """
    return f"{settings.DISPLAY_BASE_URL}/display/{slug}/"
