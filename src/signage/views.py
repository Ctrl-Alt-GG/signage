from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe

from signage.models import DisplaySettings


@require_safe
def display_root(request):
    slug = DisplaySettings.get_solo().default_screen_slug or settings.SIGNAGE_DEFAULT_SCREEN
    return redirect("signage:display", slug=slug)


@require_safe
def display(request, slug: str):
    """The kiosk page. The React app mounts here and polls the bundle API."""
    return render(request, "signage/display.html", {"screen_slug": slug})
