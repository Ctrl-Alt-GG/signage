from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from signage.api.serializers import (
    ActiveAnnouncementsSerializer,
    BundleSerializer,
    PhaseSerializer,
    ScheduleViewSerializer,
    ScreenListItemSerializer,
    ScreenSerializer,
)
from signage.integrations.base import EXPECTED_ERRORS
from signage.integrations.streams import StreamsClient
from signage.models import DisplaySettings, Event, Screen
from signage.rendering.bundle import active_announcements, announcement_view, build_bundle, stamp
from signage.rendering.phases import resolve_phase
from signage.rendering.schedule import build_schedule_view

BUNDLED_BACKGROUND = settings.BASE_DIR / "assets" / "background.svg"

# These two answers are files from elsewhere: an SVG an organizer uploaded and a picture
# from Streams. They are shown inside the display. Opened on their own they would be
# documents of this origin, where an SVG can run script with the admin's session, so
# browsers are told to treat them as pictures and nothing else.
INERT_FILE_HEADERS = {
    "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
    "X-Content-Type-Options": "nosniff",
}


def _inert(response: HttpResponse) -> HttpResponse:
    for name, value in INERT_FILE_HEADERS.items():
        response[name] = value
    return response


def _screen_or_404(slug: str) -> Screen:
    try:
        return Screen.objects.get(slug=slug, enabled=True)
    except Screen.DoesNotExist as error:
        raise Http404("Unknown screen") from error


def _is_staff(request) -> bool:
    return settings.DEBUG or bool(getattr(request.user, "is_staff", False))


class ScreenListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(operation_id="screen_list", responses=ScreenListItemSerializer(many=True))
    def get(self, request):
        default_slug = DisplaySettings.get_solo().default_screen_slug
        rows = [
            {**ScreenSerializer(screen).data, "is_default": screen.slug == default_slug}
            for screen in Screen.objects.filter(enabled=True)
        ]
        return Response(rows)


class BundleView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        operation_id="screen_bundle",
        responses=BundleSerializer,
        parameters=[
            OpenApiParameter("preview", str, description="Slide key to render alone (staff)."),
            OpenApiParameter("lang", str, description="hu, en or both (preview only)."),
            OpenApiParameter("phase", str, description="Phase key override (staff only)."),
        ],
    )
    def get(self, request, slug: str):
        screen = _screen_or_404(slug)
        now = timezone.now()
        preview = request.GET.get("preview") or None
        phase_override = request.GET.get("phase") or None
        if phase_override and not _is_staff(request):
            phase_override = None
        # A preview shows a slide whether or not it is enabled or in the current phase,
        # which is for the people who edit slides.
        if preview and not _is_staff(request):
            raise PermissionDenied("Sign in to the admin to preview a slide.")

        if preview or phase_override:
            bundle = build_bundle(
                screen,
                now,
                preview_slide=preview,
                preview_lang=request.GET.get("lang") or None,
                phase_override=phase_override,
            )
        else:
            # What every screen asks for, every few seconds. Built once and shared for a
            # moment, however many screens ask and whoever else does.
            key = f"signage:bundle:{screen.pk}"
            bundle = cache.get(key)
            if bundle is None:
                bundle = build_bundle(screen, now)
                cache.set(key, bundle, settings.SIGNAGE_BUNDLE_CACHE_SECONDS)

        response = Response(stamp(bundle, now))
        response["Cache-Control"] = "no-store"
        return response


class ScheduleView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(operation_id="schedule_view", responses=ScheduleViewSerializer)
    def get(self, request):
        event = Event.get_solo()
        return Response(build_schedule_view(event, timezone.now()).as_dict())


class PhaseView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(operation_id="phase_current", responses=PhaseSerializer)
    def get(self, request):
        event = Event.get_solo()
        phase = resolve_phase(event, timezone.now())
        if phase is None:
            raise Http404("No phases configured")
        return Response({"key": phase.key, "name": phase.pair("name"), "mode": event.phase_mode})


class ActiveAnnouncementsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(operation_id="announcements_active", responses=ActiveAnnouncementsSerializer)
    def get(self, request):
        rows = [
            {**announcement_view(a), "screens": [screen.slug for screen in a.screens.all()]}
            for a in active_announcements(timezone.now())
        ]
        return Response({"results": rows})


def background(request) -> HttpResponse:
    """The SVG background: the admin upload when present, else the bundled artwork."""
    display = DisplaySettings.get_solo()
    handle = None
    if display.background:
        try:
            handle = display.background.open("rb")
        except OSError:
            # The row outlived its file, as after restoring a database without the
            # uploads. Every screen would lose its background over it.
            handle = None
    response = FileResponse(handle or BUNDLED_BACKGROUND.open("rb"), content_type="image/svg+xml")
    # The bundle names this address with the version of the artwork, so a copy can be
    # kept for as long as the address stays the same.
    versioned = request.GET.get("v") == display.background_version
    response["Cache-Control"] = "public, max-age=86400" if versioned else "no-cache"
    return _inert(response)


def thumbnail(request, stream_id: str) -> HttpResponse:
    """Proxy a live stream thumbnail so kiosks only ever talk to the signage host."""
    client = StreamsClient()
    source = client.thumbnail_source(stream_id) if client.enabled else None
    if not source:
        raise Http404("Unknown stream")
    key = f"signage:thumbnail:{client.cache_key}:{stream_id}"
    cached = cache.get(key)
    if cached is None:
        try:
            cached = client.fetch_bytes(source)
        except EXPECTED_ERRORS as error:
            raise Http404("Thumbnail unavailable") from error
        cache.set(key, cached, settings.SIGNAGE_THUMBNAIL_CACHE_SECONDS)
    response = HttpResponse(cached[0], content_type=cached[1])
    response["Cache-Control"] = f"public, max-age={settings.SIGNAGE_THUMBNAIL_CACHE_SECONDS}"
    return _inert(response)
