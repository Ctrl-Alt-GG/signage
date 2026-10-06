"""Content and configuration models. Everything an organizer touches lives here and is
edited through the Django admin; `manage.py loadcontent` only seeds it from content/*.yaml."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from solo.models import SingletonModel

LANGS = ("hu", "en")
PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")
HEX_COLOR = RegexValidator(r"^#[0-9a-fA-F]{6}$", _("Use a six digit hex colour like #aa0000."))


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Bilingual:
    """Helpers for models with `<field>_hu` and `<field>_en` columns."""

    def text(self, field: str, lang: str) -> str:
        value = getattr(self, f"{field}_{lang}", "") or ""
        return value or getattr(self, f"{field}_hu", "") or ""

    def pair(self, field: str) -> dict[str, str]:
        return {lang: getattr(self, f"{field}_{lang}", "") or "" for lang in LANGS}


class Phase(TimeStamped, Bilingual):
    key = models.SlugField(unique=True)
    name_hu = models.CharField(max_length=60)
    name_en = models.CharField(max_length=60)
    starts = models.TimeField(help_text=_("Local wall-clock time when this phase begins."))
    day_offset = models.SmallIntegerField(
        default=0, help_text=_("0 on the event's first day, 1 after midnight.")
    )
    order = models.SmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "day_offset", "starts")

    def __str__(self) -> str:
        return self.key

    def boundary(self, event: Event) -> datetime:
        tz = event.tz
        first_day = event.starts_at.astimezone(tz).date()
        local = datetime.combine(first_day + timedelta(days=self.day_offset), self.starts)
        return local.replace(tzinfo=tz)


class Event(SingletonModel, Bilingual):
    class PhaseMode(models.TextChoices):
        MANUAL = "manual", _("Manual")
        AUTO = "auto", _("From the clock")

    name = models.CharField(max_length=100, default="Ctrl-Alt-GG")
    tagline = models.CharField(max_length=100, blank=True, default="GL&HF, IRL.")
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(default=timezone.now)
    timezone = models.CharField(max_length=60, default="Europe/Budapest")

    venue_name = models.CharField(max_length=120, blank=True)
    venue_address = models.CharField(max_length=200, blank=True)
    venue_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    venue_lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    entrance_note_hu = models.TextField(blank=True)
    entrance_note_en = models.TextField(blank=True)
    parking_hu = models.TextField(blank=True)
    parking_en = models.TextField(blank=True)
    assembly_point_hu = models.CharField(max_length=200, blank=True)
    assembly_point_en = models.CharField(max_length=200, blank=True)

    wifi_ssid = models.CharField(max_length=64, blank=True)
    wifi_password = models.CharField(max_length=128, blank=True)
    wifi_security = models.CharField(
        max_length=6,
        choices=[("WPA", "WPA/WPA2/WPA3"), ("WEP", "WEP"), ("nopass", _("Open"))],
        default="WPA",
    )
    wifi_note_hu = models.CharField(max_length=200, blank=True)
    wifi_note_en = models.CharField(max_length=200, blank=True)

    links = models.JSONField(default=dict, blank=True, help_text=_("Mapping of key to URL."))
    email = models.EmailField(blank=True)
    organizers = models.JSONField(default=list, blank=True, help_text=_("List of names."))

    phase_mode = models.CharField(max_length=6, choices=PhaseMode, default=PhaseMode.MANUAL)
    current_phase = models.ForeignKey(
        Phase, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = _("Event")

    def __str__(self) -> str:
        return self.name

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def clean(self) -> None:
        super().clean()
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as error:
            raise ValidationError({"timezone": _("Unknown IANA time zone.")}) from error
        if self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": _("The event must end after it starts.")})
        if not isinstance(self.links, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in self.links.items()
        ):
            raise ValidationError({"links": _("Links must map string keys to URL strings.")})
        if not isinstance(self.organizers, list):
            raise ValidationError({"organizers": _("Organizers must be a list of names.")})

    def placeholder_values(self, lang: str) -> dict[str, str]:
        local_start = self.starts_at.astimezone(self.tz)
        if lang == "hu":
            date_text = local_start.strftime("%Y. %m. %d.")
        else:
            date_text = f"{local_start.day} {local_start.strftime('%B %Y')}"
        return {
            "wifi_ssid": self.wifi_ssid,
            "wifi_password": self.wifi_password,
            "wifi_note": self.text("wifi_note", lang),
            "venue_name": self.venue_name,
            "venue_address": self.venue_address,
            "starts_at_time": local_start.strftime("%H:%M"),
            "starts_at_date": date_text,
            "assembly_point": self.text("assembly_point", lang),
            "email": self.email,
        }


def _validate_svg(upload) -> None:
    name = getattr(upload, "name", "") or ""
    if not name.lower().endswith(".svg"):
        raise ValidationError(_("The background must be an SVG file."))
    head = upload.read(2048)
    upload.seek(0)
    if b"<svg" not in head:
        raise ValidationError(_("The file does not look like an SVG document."))


class DisplaySettings(SingletonModel):
    background = models.FileField(
        upload_to="background/",
        blank=True,
        validators=[_validate_svg],
        help_text=_("1920x1080 SVG. Leave empty to use the bundled artwork."),
    )
    default_screen_slug = models.SlugField(default="main")
    stage_width = models.PositiveSmallIntegerField(default=1920)
    stage_height = models.PositiveSmallIntegerField(default=1080)
    safe_x = models.PositiveSmallIntegerField(default=96)
    safe_y = models.PositiveSmallIntegerField(default=204)
    safe_width = models.PositiveSmallIntegerField(default=1728)
    safe_height = models.PositiveSmallIntegerField(default=564)

    class Meta:
        verbose_name = _("Display settings")

    def __str__(self) -> str:
        return "Display settings"


class Game(TimeStamped):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    short = models.CharField(max_length=40)
    hosted = models.BooleanField(default=False)
    tournament = models.BooleanField(default=False)
    projectile_keys = models.JSONField(
        default=list, blank=True, help_text=_("Game keys the Projectile server list uses.")
    )
    color_bg = models.CharField(max_length=7, default="#777777", validators=[HEX_COLOR])
    color_text = models.CharField(max_length=7, default="#000000", validators=[HEX_COLOR])

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.projectile_keys, list) or not all(
            isinstance(k, str) for k in self.projectile_keys
        ):
            raise ValidationError({"projectile_keys": _("Must be a list of strings.")})


class ScheduleEntry(TimeStamped, Bilingual):
    class Type(models.TextChoices):
        PLAY = "play", _("Play")
        BREAK = "break", _("Break")
        HIGHLIGHT = "highlight", _("Highlight")

    time = models.TimeField()
    day_offset = models.SmallIntegerField(default=0)
    type = models.CharField(max_length=9, choices=Type, default=Type.PLAY)
    game = models.ForeignKey(Game, null=True, blank=True, on_delete=models.SET_NULL)
    label = models.CharField(max_length=60, blank=True)
    title_hu = models.CharField(max_length=120)
    title_en = models.CharField(max_length=120)
    note_hu = models.CharField(max_length=200, blank=True)
    note_en = models.CharField(max_length=200, blank=True)
    order = models.SmallIntegerField(default=0)

    class Meta:
        ordering = ("day_offset", "time", "order")
        verbose_name_plural = _("Schedule entries")

    def __str__(self) -> str:
        return f"{self.time:%H:%M} {self.title_hu}"

    def starts_at(self, event: Event) -> datetime:
        first_day = event.starts_at.astimezone(event.tz).date()
        local = datetime.combine(first_day + timedelta(days=self.day_offset), self.time)
        return local.replace(tzinfo=event.tz)


class Slide(TimeStamped, Bilingual):
    class Layout(models.TextChoices):
        HERO = "hero", "hero"
        LIST = "list", "list"
        SPLIT = "split", "split"
        QR = "qr", "qr"
        CREDENTIALS = "credentials", "credentials"
        NOW_NEXT = "now_next", "now_next"
        SCHEDULE = "schedule", "schedule"
        SERVERS = "servers", "servers"
        TOURNAMENT = "tournament", "tournament"
        STREAMS = "streams", "streams"
        COUNTDOWN = "countdown", "countdown"

    class Source(models.TextChoices):
        STATIC = "static", _("Static text")
        SCHEDULE = "live:schedule", _("Live: schedule")
        CLOCK = "live:clock", _("Live: clock")
        PROJECTILE = "live:projectile", _("Live: Projectile servers")
        BRACKET = "live:bracket", _("Live: Bracket tournament")
        STREAMS = "live:streams", _("Live: Streams")

    class BilingualMode(models.TextChoices):
        ALTERNATE = "alternate", _("Hungarian pass, then English pass")
        STACKED = "stacked", _("Both languages on one pass")

    class Origin(models.TextChoices):
        SEED = "seed", _("Seeded from YAML")
        ADMIN = "admin", _("Edited in the admin")

    key = models.SlugField(primary_key=True, max_length=60)
    layout = models.CharField(max_length=12, choices=Layout)
    source = models.CharField(max_length=16, choices=Source, default=Source.STATIC)
    all_phases = models.BooleanField(default=False)
    phases = models.ManyToManyField(Phase, blank=True, related_name="slides")
    duration_seconds = models.PositiveSmallIntegerField(
        default=15, validators=[MinValueValidator(5), MaxValueValidator(120)]
    )
    bilingual_mode = models.CharField(
        max_length=9, choices=BilingualMode, default=BilingualMode.ALTERNATE
    )
    priority = models.SmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    order = models.SmallIntegerField(default=0)
    enabled = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    kicker_hu = models.CharField(max_length=80, blank=True)
    kicker_en = models.CharField(max_length=80, blank=True)
    title_hu = models.CharField(max_length=120)
    title_en = models.CharField(max_length=120, blank=True)
    body_hu = models.TextField(blank=True)
    body_en = models.TextField(blank=True)
    footer_hu = models.CharField(max_length=200, blank=True)
    footer_en = models.CharField(max_length=200, blank=True)
    empty_hu = models.CharField(max_length=200, blank=True)
    empty_en = models.CharField(max_length=200, blank=True)
    column1_title_hu = models.CharField(max_length=80, blank=True)
    column1_title_en = models.CharField(max_length=80, blank=True)
    column2_title_hu = models.CharField(max_length=80, blank=True)
    column2_title_en = models.CharField(max_length=80, blank=True)
    labels = models.JSONField(
        default=dict, blank=True, help_text=_("Section or column labels, bilingual, by key.")
    )
    link_url = models.CharField(
        max_length=500, blank=True, help_text=_("URL for the QR code. `wifi` encodes the Wi-Fi.")
    )
    link_label_hu = models.CharField(max_length=120, blank=True)
    link_label_en = models.CharField(max_length=120, blank=True)
    link_qr = models.BooleanField(default=False)
    notes = models.TextField(blank=True, help_text=_("Author notes. Never shown."))
    origin = models.CharField(max_length=5, choices=Origin, default=Origin.SEED)

    class Meta:
        ordering = ("-priority", "order", "key")

    def __str__(self) -> str:
        return self.key

    @property
    def is_live(self) -> bool:
        return self.source != self.Source.STATIC

    def clean(self) -> None:
        super().clean()
        if self.layout == self.Layout.SPLIT and not (
            self.column1_title_hu and self.column2_title_hu
        ):
            raise ValidationError(_("A split slide needs both column titles."))
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": _("Must be after valid from.")})
        if not isinstance(self.labels, dict):
            raise ValidationError({"labels": _("Labels must be a mapping.")})
        for key, value in self.labels.items():
            if not isinstance(value, dict) or not all(isinstance(value.get(x), str) for x in LANGS):
                raise ValidationError(
                    {"labels": _("Label %(key)s needs hu and en.") % {"key": key}}
                )

    def in_phase(self, phase: Phase | None) -> bool:
        if self.all_phases or phase is None:
            return True
        return self.phases.filter(pk=phase.pk).exists()

    def is_valid_at(self, now: datetime) -> bool:
        if self.valid_from and now < self.valid_from:
            return False
        return not (self.valid_until and now >= self.valid_until)


class SlideItem(models.Model):
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name="items")
    column = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(2)]
    )
    order = models.SmallIntegerField(default=0)
    text_hu = models.CharField(max_length=240)
    text_en = models.CharField(max_length=240)
    icon = models.CharField(max_length=40, blank=True, help_text=_("Lucide icon name."))

    class Meta:
        ordering = ("column", "order", "id")

    def __str__(self) -> str:
        return self.text_hu[:40]


class Screen(TimeStamped):
    class LanguageMode(models.TextChoices):
        SLIDE = "slide", _("Follow each slide")
        HU = "hu", "Magyar"
        EN = "en", "English"

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    enabled = models.BooleanField(default=True)
    refresh_seconds = models.PositiveSmallIntegerField(
        default=20, validators=[MinValueValidator(5), MaxValueValidator(600)]
    )
    language_mode = models.CharField(max_length=5, choices=LanguageMode, default=LanguageMode.SLIDE)
    show_clock = models.BooleanField(default=True)
    show_progress = models.BooleanField(default=True)
    slides = models.ManyToManyField(
        Slide,
        through="ScreenSlide",
        blank=True,
        related_name="screens",
        help_text=_("Leave empty to show every slide of the current phase."),
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("slug",)

    def __str__(self) -> str:
        return self.name


class ScreenSlide(models.Model):
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE)
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE)
    order = models.SmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")
        unique_together = (("screen", "slide"),)

    def __str__(self) -> str:
        return f"{self.screen_id}:{self.slide_id}"


class AnnouncementTemplate(TimeStamped, Bilingual):
    class Level(models.TextChoices):
        INFO = "info", _("Info")
        WARNING = "warning", _("Warning")
        URGENT = "urgent", _("Urgent")

    key = models.SlugField(unique=True)
    level = models.CharField(max_length=7, choices=Level, default=Level.INFO)
    takeover = models.BooleanField(default=False)
    text_hu = models.CharField(max_length=300)
    text_en = models.CharField(max_length=300)

    class Meta:
        ordering = ("key",)

    def __str__(self) -> str:
        return self.key

    @property
    def placeholders(self) -> list[str]:
        found: list[str] = []
        for text in (self.text_hu, self.text_en):
            for name in PLACEHOLDER_RE.findall(text):
                if name not in found:
                    found.append(name)
        return found


class Announcement(TimeStamped, Bilingual):
    Level = AnnouncementTemplate.Level

    text_hu = models.CharField(max_length=300)
    text_en = models.CharField(max_length=300)
    level = models.CharField(max_length=7, choices=Level, default=Level.INFO)
    takeover = models.BooleanField(
        default=False, help_text=_("Replace the rotation while active instead of showing a bar.")
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True, help_text=_("Empty means until ended."))
    enabled = models.BooleanField(default=True)
    screens = models.ManyToManyField(
        Screen, blank=True, related_name="announcements", help_text=_("Empty means every screen.")
    )
    template = models.ForeignKey(
        AnnouncementTemplate, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, editable=False
    )

    class Meta:
        ordering = ("-starts_at",)

    def __str__(self) -> str:
        return self.text_hu[:60]

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or timezone.now()
        if not self.enabled or self.starts_at > now:
            return False
        return self.ends_at is None or self.ends_at > now


class Integration(TimeStamped):
    """Connection settings for one upstream system. One row per kind, created by the
    initial migration; organizers fill in the URL and credentials in the admin."""

    class Kind(models.TextChoices):
        PROJECTILE = "projectile", _("Projectile game server list")
        BRACKET = "bracket", _("Bracket tournament system")
        STREAMS = "streams", _("Streams directory")

    class Auth(models.TextChoices):
        NONE = "none", _("No authentication")
        BASIC = "basic", _("HTTP Basic (username and password)")
        BEARER = "bearer", _("Bearer token")
        HEADER = "header", _("Custom header")

    kind = models.CharField(max_length=10, choices=Kind, unique=True)
    enabled = models.BooleanField(default=False)
    base_url = models.URLField(
        blank=True,
        help_text=_(
            "API root without a trailing slash, for example https://servers.ctrl-alt-gg.hu/api"
        ),
    )
    auth_type = models.CharField(max_length=6, choices=Auth, default=Auth.NONE)
    username = models.CharField(max_length=120, blank=True)
    password = models.CharField(max_length=240, blank=True)
    token = models.CharField(max_length=500, blank=True)
    header_name = models.CharField(max_length=60, blank=True, default="Authorization")
    verify_tls = models.BooleanField(default=True)
    ca_bundle = models.CharField(
        max_length=300, blank=True, help_text=_("Path to a CA bundle for a venue certificate.")
    )
    connect_timeout = models.FloatField(default=2.0)
    read_timeout = models.FloatField(default=4.0)
    cache_seconds = models.PositiveSmallIntegerField(
        default=15, validators=[MinValueValidator(1), MaxValueValidator(600)]
    )
    tournament_id = models.PositiveIntegerField(
        null=True, blank=True, help_text=_("Bracket only. Empty picks the first open tournament.")
    )
    mirror_announcement = models.BooleanField(
        default=False, help_text=_("Projectile only. Show its announcement as an info bar.")
    )

    class Meta:
        ordering = ("kind",)

    def __str__(self) -> str:
        return self.get_kind_display()

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.base_url)

    def clean(self) -> None:
        super().clean()
        if self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")
        if self.auth_type == self.Auth.BASIC and not (self.username and self.password):
            raise ValidationError(_("Basic authentication needs a username and a password."))
        if self.auth_type in (self.Auth.BEARER, self.Auth.HEADER) and not self.token:
            raise ValidationError({"token": _("This authentication type needs a token.")})

    def auth_headers(self) -> dict[str, str]:
        if self.auth_type == self.Auth.BEARER:
            return {"Authorization": f"Bearer {self.token}"}
        if self.auth_type == self.Auth.HEADER:
            return {self.header_name or "Authorization": self.token}
        return {}

    def basic_auth(self) -> tuple[str, str] | None:
        if self.auth_type == self.Auth.BASIC:
            return (self.username, self.password)
        return None
