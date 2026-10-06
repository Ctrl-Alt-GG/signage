from __future__ import annotations

import mimetypes

from django.conf import settings
from django.core.cache import cache
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotModified
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from signage.api.serializers import (
    ActiveAnnouncementsSerializer,
    BundleSerializer,
    PhaseSerializer,
    ScheduleViewSerializer,
    ScreenSerializer,
)
from signage.integrations.streams import StreamsClient
from signage.models import Announcement, DisplaySettings, Event, Screen
from signage.rendering.bundle import build_bundle
from signage.rendering.phases import resolve_phase
from signage.rendering.schedule import build_schedule_view

BUNDLED_BACKGROUND = settings.BASE_DIR / "assets" / "background.svg"


def _screen_or_404(slug: str) -> Screen:
    try:
        return Screen.objects.get(slug=slug, enabled=True)
    except Screen.DoesNotExist as error:
        raise Http404("Unknown screen") from error


class ScreenListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(operation_id="screen_list", responses=ScreenSerializer(many=True))
    def get(self, request):
        screens = Screen.objects.filter(enabled=True)
        return Response(ScreenSerializer(screens, many=True).data)


class BundleView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        operation_id="screen_bundle",
        responses=BundleSerializer,
        parameters=[
            OpenApiParameter("preview", str, description="Slide key to render alone."),
            OpenApiParameter("lang", str, description="hu, en or both (preview only)."),
            OpenApiParameter("phase", str, description="Phase key override (staff only)."),
        ],
    )
    def get(self, request, slug: str):
        screen = _screen_or_404(slug)
        phase_override = request.GET.get("phase") or None
        if phase_override and not (settings.DEBUG or getattr(request.user, "is_staff", False)):
            phase_override = None
        bundle = build_bundle(
            screen,
            timezone.now(),
            preview_slide=request.GET.get("preview") or None,
            preview_lang=request.GET.get("lang") or None,
            phase_override=phase_override,
        )
        etag = f'"{bundle["version"]}"'
        if request.headers.get("If-None-Match") == etag:
            return HttpResponseNotModified()
        response = Response(bundle)
        response["ETag"] = etag
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
        now = timezone.now()
        rows = [
            {
                "id": a.pk,
                "level": a.level,
                "takeover": a.takeover,
                "text": a.pair("text"),
                "ends_at": a.ends_at,
                "screens": [s.slug for s in a.screens.all()],
            }
            for a in Announcement.objects.filter(enabled=True, starts_at__lte=now)
            if a.is_active(now)
        ]
        return Response({"results": rows})


def background(request) -> HttpResponse:
    """The SVG background: the admin upload when present, else the bundled artwork."""
    display = DisplaySettings.get_solo()
    if display.background:
        handle = display.background.open("rb")
        response = FileResponse(handle, content_type="image/svg+xml")
        response["Cache-Control"] = "public, max-age=60"
        return response
    response = FileResponse(BUNDLED_BACKGROUND.open("rb"), content_type="image/svg+xml")
    response["Cache-Control"] = "public, max-age=3600"
    return response


def thumbnail(request, stream_id: str) -> HttpResponse:
    """Proxy a live stream thumbnail so kiosks only ever talk to the signage host."""
    client = StreamsClient()
    source = client.thumbnail_source(stream_id)
    if not source or not client.enabled:
        raise Http404("Unknown stream")
    key = f"signage:thumbnail:{stream_id}"
    cached = cache.get(key)
    if cached is None:
        try:
            content, content_type = client.fetch_bytes(source)
        except Exception as error:
            raise Http404("Thumbnail unavailable") from error
        cached = (content, content_type or mimetypes.guess_type(source)[0] or "image/jpeg")
        cache.set(key, cached, settings.SIGNAGE_THUMBNAIL_CACHE_SECONDS)
    response = HttpResponse(cached[0], content_type=cached[1])
    response["Cache-Control"] = f"public, max-age={settings.SIGNAGE_THUMBNAIL_CACHE_SECONDS}"
    return response
