"""Serializers describe the JSON shapes for the OpenAPI schema the frontend types are
generated from. The bundle itself is built as plain dicts in rendering/bundle.py."""

from drf_spectacular.utils import PolymorphicProxySerializer
from rest_framework import serializers

from signage.content.lint import LAYOUT_SOURCES


class BilingualSerializer(serializers.Serializer):
    hu = serializers.CharField(allow_blank=True)
    en = serializers.CharField(allow_blank=True)


class ScreenSerializer(serializers.Serializer):
    slug = serializers.SlugField()
    name = serializers.CharField()
    refresh_seconds = serializers.IntegerField()
    show_clock = serializers.BooleanField()
    show_progress = serializers.BooleanField()
    language_mode = serializers.ChoiceField(choices=("slide", "hu", "en"))


class ScreenListItemSerializer(ScreenSerializer):
    is_default = serializers.BooleanField()


class PhaseSerializer(serializers.Serializer):
    key = serializers.SlugField()
    name = BilingualSerializer()
    mode = serializers.ChoiceField(choices=("manual", "auto"), required=False)


class ClockSerializer(serializers.Serializer):
    now = serializers.DateTimeField()
    timezone = serializers.CharField()


class EventSummarySerializer(serializers.Serializer):
    name = serializers.CharField()
    tagline = serializers.CharField(allow_blank=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class SafeAreaSerializer(serializers.Serializer):
    x = serializers.IntegerField()
    y = serializers.IntegerField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()


class StageSerializer(serializers.Serializer):
    width = serializers.IntegerField()
    height = serializers.IntegerField()
    safe = SafeAreaSerializer()
    background_url = serializers.CharField()


class AnnouncementSerializer(serializers.Serializer):
    id = serializers.CharField()
    level = serializers.ChoiceField(choices=("info", "warning", "urgent"))
    takeover = serializers.BooleanField()
    text = BilingualSerializer()
    ends_at = serializers.DateTimeField(allow_null=True)


class SlideItemSerializer(BilingualSerializer):
    icon = serializers.CharField(allow_blank=True, required=False)


class SlideColumnSerializer(serializers.Serializer):
    title = BilingualSerializer()
    items = SlideItemSerializer(many=True)


class SlideLinkSerializer(serializers.Serializer):
    url = serializers.CharField(allow_blank=True)
    label = BilingualSerializer()
    qr_payload = serializers.CharField(allow_blank=True)


class WifiCredentialsSerializer(serializers.Serializer):
    ssid = serializers.CharField(trim_whitespace=False)
    password = serializers.CharField(allow_blank=True, allow_null=True, trim_whitespace=False)


class SlideContentSerializer(serializers.Serializer):
    kicker = BilingualSerializer(required=False)
    title = BilingualSerializer()
    body = BilingualSerializer(required=False)
    footer = BilingualSerializer(required=False)
    empty = BilingualSerializer(required=False)
    items = SlideItemSerializer(many=True)
    columns = SlideColumnSerializer(many=True)
    labels = serializers.DictField(child=BilingualSerializer())
    link = SlideLinkSerializer(allow_null=True, required=False)
    wifi_credentials = WifiCredentialsSerializer(allow_null=True, required=False)


class GameRefSerializer(serializers.Serializer):
    slug = serializers.SlugField()
    name = serializers.CharField()
    short = serializers.CharField()
    color_bg = serializers.CharField()
    color_text = serializers.CharField()


class ScheduleEntryViewSerializer(serializers.Serializer):
    time = serializers.CharField()
    type = serializers.ChoiceField(choices=("play", "break", "highlight"))
    label = serializers.CharField(allow_blank=True)
    title = BilingualSerializer()
    note = BilingualSerializer()
    game = GameRefSerializer(allow_null=True)
    starts_at = serializers.DateTimeField()


class ScheduleViewSerializer(serializers.Serializer):
    now = ScheduleEntryViewSerializer(many=True)
    next = ScheduleEntryViewSerializer(many=True)
    later = ScheduleEntryViewSerializer(many=True)
    upcoming = ScheduleEntryViewSerializer(many=True)


# The live data of each source, as rendering/bundle.py and src/signage/integrations make it.
# When an upstream system has nothing to show, its slide gets `{"empty": true, "stale": true}`.


class LiveSerializer(serializers.Serializer):
    # The answer stands in for one that could not be had, or is old by the upstream's word.
    stale = serializers.BooleanField(required=False)
    # The upstream had nothing to show, not even an answer from before.
    empty = serializers.BooleanField(required=False)


class CountdownLiveSerializer(serializers.Serializer):
    target = serializers.DateTimeField()
    passed = serializers.BooleanField()


class ServerCardSerializer(serializers.Serializer):
    name = serializers.CharField()
    info = serializers.CharField(allow_blank=True)
    game_slug = serializers.CharField(allow_blank=True)
    game_name = serializers.CharField()
    game_short = serializers.CharField()
    color_bg = serializers.CharField()
    color_text = serializers.CharField()
    players_text = serializers.CharField(allow_blank=True)
    online_players = serializers.IntegerField(allow_null=True, required=False)
    max_players = serializers.IntegerField(allow_null=True, required=False)


class ServersLiveSerializer(LiveSerializer):
    servers = ServerCardSerializer(many=True, required=False)
    announcement = serializers.CharField(allow_blank=True, required=False)


class MatchRowSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    team1 = serializers.CharField()
    team2 = serializers.CharField()
    score1 = serializers.IntegerField()
    score2 = serializers.IntegerField()
    start_local = serializers.CharField(allow_blank=True)
    round = serializers.CharField(allow_blank=True)
    # `awaiting`: it has started and its planned time is over, but it has no result yet.
    status = serializers.ChoiceField(
        choices=("live", "awaiting", "scheduled", "finished", "waiting")
    )


class LivePageSerializer(serializers.Serializer):
    number = serializers.IntegerField()
    count = serializers.IntegerField()
    first = serializers.IntegerField()
    last = serializers.IntegerField()
    total = serializers.IntegerField()


class TournamentLiveSerializer(LiveSerializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    name = serializers.CharField(allow_blank=True, required=False)
    live = MatchRowSerializer(many=True, required=False)
    # Which of the live matches this pass shows, when they take more than one.
    live_page = LivePageSerializer(required=False)
    upcoming = MatchRowSerializer(many=True, required=False)
    results = MatchRowSerializer(many=True, required=False)


class ChannelSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    audio_only = serializers.BooleanField()
    thumbnail_url = serializers.CharField(allow_blank=True)
    watch_url = serializers.CharField(allow_blank=True)


class StreamsLiveSerializer(LiveSerializer):
    live = ChannelSerializer(many=True, required=False)
    # Whether Streams could check its media server: `unavailable` says that it can't tell
    # which channels are live.
    source_status = serializers.ChoiceField(
        choices=("fresh", "stale", "unavailable"), required=False
    )
    observed_at = serializers.CharField(allow_null=True, required=False)
    age_seconds = serializers.FloatField(allow_null=True, required=False)


LIVE_SERIALIZERS = {
    "live:clock": CountdownLiveSerializer,
    "live:schedule": ScheduleViewSerializer,
    "live:projectile": ServersLiveSerializer,
    "live:bracket": TournamentLiveSerializer,
    "live:streams": StreamsLiveSerializer,
}


class PassBaseSerializer(serializers.Serializer):
    key = serializers.CharField()
    slide = serializers.SlugField()
    lang = serializers.ChoiceField(choices=("hu", "en", "both"))
    duration_ms = serializers.IntegerField()
    content = SlideContentSerializer()


def _pass_serializer(source: str) -> type[serializers.Serializer]:
    """A pass of `source`: the layouts that draw it, and its live data. A text slide has
    none; a live one has null in a preview when its upstream system isn't configured.

    A text pass leaves the field out rather than declaring it null: openapi-fetch's
    response types drop a property whose only type is null, and the display would then
    be typed against a pass the API does not describe."""
    layouts = sorted(layout for layout, wanted in LAYOUT_SOURCES.items() if wanted == source)
    name = "".join(part.capitalize() for part in source.replace(":", "_").split("_"))
    fields = {
        "source": serializers.ChoiceField(choices=(source,)),
        "layout": serializers.ChoiceField(choices=layouts),
    }
    if live := LIVE_SERIALIZERS.get(source):
        fields["live"] = live(allow_null=True)
    return type(f"{name}PassSerializer", (PassBaseSerializer,), fields)


PASS_SERIALIZERS = {source: _pass_serializer(source) for source in ("static", *LIVE_SERIALIZERS)}


class BundleSerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    screen = ScreenSerializer()
    phase = PhaseSerializer(allow_null=True)
    clock = ClockSerializer()
    event = EventSummarySerializer()
    stage = StageSerializer()
    announcements = AnnouncementSerializer(many=True)
    # The layout and the live data of a pass follow from its source (lint.LAYOUT_SOURCES).
    passes = PolymorphicProxySerializer(
        component_name="Pass",
        serializers=PASS_SERIALIZERS,
        resource_type_field_name="source",
        many=True,
    )
    warnings = serializers.ListField(child=serializers.CharField())
    preview = serializers.BooleanField()


class ActiveAnnouncementRowSerializer(AnnouncementSerializer):
    screens = serializers.ListField(child=serializers.SlugField())


class ActiveAnnouncementsSerializer(serializers.Serializer):
    results = ActiveAnnouncementRowSerializer(many=True)
