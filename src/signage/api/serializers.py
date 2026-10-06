"""Serializers describe the JSON shapes for the OpenAPI schema the frontend types are
generated from. The bundle itself is built as plain dicts in rendering/bundle.py."""

from rest_framework import serializers


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


class PassSerializer(serializers.Serializer):
    key = serializers.CharField()
    slide = serializers.SlugField()
    layout = serializers.CharField()
    source = serializers.CharField()
    lang = serializers.ChoiceField(choices=("hu", "en", "both"))
    duration_ms = serializers.IntegerField()
    content = SlideContentSerializer()
    live = serializers.JSONField(allow_null=True)


class BundleSerializer(serializers.Serializer):
    version = serializers.CharField()
    generated_at = serializers.DateTimeField()
    screen = ScreenSerializer()
    phase = PhaseSerializer(allow_null=True)
    clock = ClockSerializer()
    event = EventSummarySerializer()
    announcement = AnnouncementSerializer(allow_null=True)
    passes = PassSerializer(many=True)
    warnings = serializers.ListField(child=serializers.CharField())
    preview = serializers.BooleanField()
    default_screen = serializers.CharField()


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


class ActiveAnnouncementRowSerializer(AnnouncementSerializer):
    screens = serializers.ListField(child=serializers.SlugField())


class ActiveAnnouncementsSerializer(serializers.Serializer):
    results = ActiveAnnouncementRowSerializer(many=True)
