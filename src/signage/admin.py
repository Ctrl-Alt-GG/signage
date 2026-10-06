"""The Django admin is the only management UI. Everything organizers change at the event
is here: the event facts, the phase, slides, the schedule, announcements, screens, the
background artwork and the upstream connections."""

from __future__ import annotations

from typing import ClassVar

import yaml
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from solo.admin import SingletonModelAdmin

from signage.content import lint
from signage.content import loader as content_loader
from signage.integrations.bracket import BracketClient
from signage.integrations.projectile import ProjectileClient
from signage.integrations.streams import StreamsClient
from signage.models import (
    Announcement,
    AnnouncementTemplate,
    DisplaySettings,
    Event,
    Game,
    Integration,
    Phase,
    ScheduleEntry,
    Screen,
    ScreenSlide,
    Slide,
    SlideItem,
)
from signage.rendering.bundle import build_bundle
from signage.rendering.phases import resolve_phase

CLIENTS = {
    Integration.Kind.PROJECTILE: ProjectileClient,
    Integration.Kind.BRACKET: BracketClient,
    Integration.Kind.STREAMS: StreamsClient,
}

admin.site.site_header = "Ctrl-Alt-GG Signage"
admin.site.site_title = "Signage admin"
admin.site.index_title = _("Signage administration")


class YamlImportForm(forms.Form):
    file = forms.FileField(label=_("YAML file"))
    overwrite = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Overwrite rows edited in the admin"),
    )


class YamlImportMixin:
    """Adds an "Import from YAML" button and view to a model admin. Subclasses set
    `yaml_loader` to a function taking the parsed document and returning a Report."""

    yaml_loader = None
    yaml_name = ""
    change_list_template = "admin/signage/change_list_with_import.html"

    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom = [
            path(
                "import-yaml/",
                self.admin_site.admin_view(self.import_yaml_view),
                name="{}_{}_import_yaml".format(*info),
            )
        ]
        return [*custom, *urls]

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        info = self.model._meta.app_label, self.model._meta.model_name
        extra_context["import_yaml_url"] = reverse("admin:{}_{}_import_yaml".format(*info))
        extra_context["import_yaml_name"] = self.yaml_name
        return super().changelist_view(request, extra_context=extra_context)

    def import_yaml_view(self, request):
        form = YamlImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            text = form.cleaned_data["file"].read().decode("utf-8")
            try:
                lint.lint_text(text, form.cleaned_data["file"].name)
                data = yaml.safe_load(text) or {}
                report = self.run_yaml_loader(data, overwrite=form.cleaned_data["overwrite"])
            except (lint.LintError, yaml.YAMLError, KeyError, TypeError) as error:
                messages.error(request, _("Import failed: %(error)s") % {"error": error})
            else:
                messages.success(request, report.summary())
                for item in report.skipped:
                    messages.warning(request, _("Skipped %(item)s") % {"item": item})
                info = self.model._meta.app_label, self.model._meta.model_name
                return redirect("admin:{}_{}_changelist".format(*info))
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "opts": self.model._meta,
            "title": _("Import %(name)s from YAML") % {"name": self.yaml_name},
        }
        return TemplateResponse(request, "admin/signage/import_yaml.html", context)

    def run_yaml_loader(self, data, *, overwrite):
        return type(self).yaml_loader(data, overwrite=overwrite)


def _slides_loader(data, *, overwrite):
    return content_loader.load_slides(data, overwrite=overwrite)


def _schedule_loader(data, *, overwrite):
    return content_loader.load_schedule(data)


def _games_loader(data, *, overwrite):
    return content_loader.load_games(data)


def _announcements_loader(data, *, overwrite):
    return content_loader.load_announcements(data)


def _event_loader(data, *, overwrite):
    return content_loader.load_event(data, overwrite=overwrite)


@admin.register(Event)
class EventAdmin(YamlImportMixin, SingletonModelAdmin):
    yaml_loader = staticmethod(_event_loader)
    yaml_name = "event.yaml"
    change_list_template = None
    fieldsets = (
        (_("Event"), {"fields": ("name", "tagline", "starts_at", "ends_at", "timezone")}),
        (
            _("Phase"),
            {
                "fields": ("phase_mode", "current_phase", "resolved_phase"),
                "description": _(
                    "Manual mode shows the chosen phase. Auto mode follows the clock using "
                    "the phase start times."
                ),
            },
        ),
        (
            _("Venue"),
            {
                "fields": (
                    "venue_name",
                    "venue_address",
                    ("venue_lat", "venue_lng"),
                    ("entrance_note_hu", "entrance_note_en"),
                    ("parking_hu", "parking_en"),
                    ("assembly_point_hu", "assembly_point_en"),
                )
            },
        ),
        (
            _("Wi-Fi"),
            {
                "fields": (
                    "wifi_ssid",
                    "wifi_password",
                    "wifi_security",
                    ("wifi_note_hu", "wifi_note_en"),
                )
            },
        ),
        (_("Contact and links"), {"fields": ("email", "organizers", "links")}),
    )
    readonly_fields = ("resolved_phase",)

    @admin.display(description=_("Phase in force now"))
    def resolved_phase(self, obj):
        phase = resolve_phase(obj, timezone.now()) if obj.pk else None
        return phase.key if phase else "-"

    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom = [
            path(
                "import-yaml/",
                self.admin_site.admin_view(self.import_yaml_view),
                name="{}_{}_import_yaml".format(*info),
            ),
            path(
                "set-phase/<slug:key>/",
                self.admin_site.admin_view(self.set_phase_view),
                name="{}_{}_set_phase".format(*info),
            ),
        ]
        return [*custom, *urls]

    def set_phase_view(self, request, key: str):
        event = Event.get_solo()
        phase = Phase.objects.filter(key=key).first()
        if request.method == "POST" and phase:
            event.phase_mode = Event.PhaseMode.MANUAL
            event.current_phase = phase
            event.save(update_fields=["phase_mode", "current_phase"])
            messages.success(request, _("Phase set to %(key)s") % {"key": key})
        return redirect("admin:signage_event_change")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["phases"] = Phase.objects.order_by("order")
        extra_context["import_yaml_url"] = reverse("admin:signage_event_import_yaml")
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    change_form_template = "admin/signage/event_change_form.html"


@admin.register(DisplaySettings)
class DisplaySettingsAdmin(SingletonModelAdmin):
    fieldsets = (
        (_("Background"), {"fields": ("background", "background_preview")}),
        (_("Screens"), {"fields": ("default_screen_slug",)}),
        (
            _("Stage geometry"),
            {
                "classes": ("collapse",),
                "fields": (
                    ("stage_width", "stage_height"),
                    ("safe_x", "safe_y"),
                    ("safe_width", "safe_height"),
                ),
            },
        ),
    )
    readonly_fields = ("background_preview",)

    @admin.display(description=_("Preview"))
    def background_preview(self, obj):
        url = reverse("signage-api:background")
        return format_html(
            '<img src="{}" alt="" style="max-width:480px;border:1px solid #444;border-radius:8px">',
            url,
        )


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("key", "name_hu", "name_en", "starts", "day_offset", "order")
    list_editable = ("starts", "day_offset", "order")
    ordering = ("order",)


@admin.register(Game)
class GameAdmin(YamlImportMixin, admin.ModelAdmin):
    yaml_loader = staticmethod(_games_loader)
    yaml_name = "games.yaml"
    list_display = ("name", "slug", "short", "hosted", "tournament", "swatch")
    list_editable = ("hosted", "tournament")
    search_fields = ("name", "slug", "short")
    list_filter = ("hosted", "tournament")

    @admin.display(description=_("Colour"))
    def swatch(self, obj):
        style = "display:inline-block;padding:2px 10px;border-radius:999px;background:{};color:{}"
        return format_html(
            '<span style="' + style + '">{}</span>',
            obj.color_bg,
            obj.color_text,
            obj.short,
        )


@admin.register(ScheduleEntry)
class ScheduleEntryAdmin(YamlImportMixin, admin.ModelAdmin):
    yaml_loader = staticmethod(_schedule_loader)
    yaml_name = "schedule.yaml"
    list_display = ("local_start", "type", "label", "title_hu", "title_en", "game")
    list_editable = ("type",)
    list_filter = ("type", "day_offset", "game")
    search_fields = ("title_hu", "title_en", "label")
    ordering = ("day_offset", "time", "order")
    fieldsets = (
        (None, {"fields": (("time", "day_offset"), "type", ("game", "label"), "order")}),
        (_("Text"), {"fields": (("title_hu", "title_en"), ("note_hu", "note_en"))}),
    )

    @admin.display(description=_("Starts"), ordering="time")
    def local_start(self, obj):
        event = Event.get_solo()
        return obj.starts_at(event).strftime("%a %H:%M")


class SlideItemInline(admin.TabularInline):
    model = SlideItem
    extra = 0
    fields = ("column", "order", "text_hu", "text_en", "icon")
    ordering = ("column", "order")


class ScreenSlideInline(admin.TabularInline):
    model = ScreenSlide
    extra = 0
    autocomplete_fields = ("slide",)
    ordering = ("order",)


@admin.register(Slide)
class SlideAdmin(YamlImportMixin, admin.ModelAdmin):
    yaml_loader = staticmethod(_slides_loader)
    yaml_name = "slides.yaml"
    list_display = (
        "key",
        "layout",
        "source",
        "phase_list",
        "enabled",
        "priority",
        "duration_seconds",
        "bilingual_mode",
        "origin",
        "preview_links",
    )
    list_editable = ("enabled", "priority", "duration_seconds")
    list_filter = (
        "layout",
        "source",
        "enabled",
        "bilingual_mode",
        "all_phases",
        "phases",
        "origin",
    )
    search_fields = ("key", "title_hu", "title_en", "body_hu", "body_en")
    filter_horizontal = ("phases",)
    inlines = (SlideItemInline,)
    actions = ("enable_slides", "disable_slides")
    fieldsets = (
        (None, {"fields": ("key", "layout", "source", "enabled", "origin")}),
        (
            _("Rotation"),
            {
                "fields": (
                    ("all_phases", "phases"),
                    ("duration_seconds", "bilingual_mode", "priority", "order"),
                    ("valid_from", "valid_until"),
                )
            },
        ),
        (
            _("Text"),
            {
                "fields": (
                    ("kicker_hu", "kicker_en"),
                    ("title_hu", "title_en"),
                    ("body_hu", "body_en"),
                    ("footer_hu", "footer_en"),
                    ("empty_hu", "empty_en"),
                )
            },
        ),
        (
            _("Split columns"),
            {
                "classes": ("collapse",),
                "fields": (
                    ("column1_title_hu", "column1_title_en"),
                    ("column2_title_hu", "column2_title_en"),
                ),
            },
        ),
        (_("Link and QR"), {"fields": ("link_url", ("link_label_hu", "link_label_en"), "link_qr")}),
        (_("Advanced"), {"classes": ("collapse",), "fields": ("labels", "notes")}),
    )

    def get_readonly_fields(self, request, obj=None):
        return ("key", "origin") if obj else ("origin",)

    @admin.display(description=_("Phases"))
    def phase_list(self, obj):
        return "all" if obj.all_phases else ", ".join(p.key for p in obj.phases.all())

    @admin.display(description=_("Preview"))
    def preview_links(self, obj):
        screen = DisplaySettings.get_solo().default_screen_slug
        base = reverse("signage:display", kwargs={"slug": screen})
        return format_html(
            '<a href="{}?preview={}&lang=hu" target="_blank">HU</a> | '
            '<a href="{}?preview={}&lang=en" target="_blank">EN</a>',
            base,
            obj.key,
            base,
            obj.key,
        )

    @admin.action(description=_("Enable selected slides"))
    def enable_slides(self, request, queryset):
        queryset.update(enabled=True)

    @admin.action(description=_("Disable selected slides"))
    def disable_slides(self, request, queryset):
        queryset.update(enabled=False)

    def save_model(self, request, obj, form, change):
        obj.origin = Slide.Origin.ADMIN
        super().save_model(request, obj, form, change)


@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "enabled", "refresh_seconds", "language_mode", "open_link")
    list_editable = ("enabled", "refresh_seconds", "language_mode")
    inlines = (ScreenSlideInline,)
    prepopulated_fields: ClassVar[dict] = {"slug": ("name",)}

    @admin.display(description=_("Display"))
    def open_link(self, obj):
        url = reverse("signage:display", kwargs={"slug": obj.slug})
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)


@admin.register(AnnouncementTemplate)
class AnnouncementTemplateAdmin(YamlImportMixin, admin.ModelAdmin):
    yaml_loader = staticmethod(_announcements_loader)
    yaml_name = "announcements.yaml"
    list_display = ("key", "level", "takeover", "text_hu", "placeholder_list")
    list_filter = ("level", "takeover")

    @admin.display(description=_("Placeholders"))
    def placeholder_list(self, obj):
        return ", ".join(obj.placeholders) or "-"


class AnnouncementFromTemplateForm(forms.Form):
    template = forms.ModelChoiceField(queryset=AnnouncementTemplate.objects.all())
    duration_minutes = forms.ChoiceField(
        choices=((10, "10"), (30, "30"), (60, "60"), (0, _("until ended"))), initial=10
    )
    screens = forms.ModelMultipleChoiceField(
        queryset=Screen.objects.filter(enabled=True), required=False
    )

    def __init__(self, *args, placeholders=(), **kwargs):
        super().__init__(*args, **kwargs)
        for name in placeholders:
            self.fields[f"ph_{name}"] = forms.CharField(label=name, max_length=120)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("text_hu", "level", "takeover", "active_now", "starts_at", "ends_at", "enabled")
    list_filter = ("level", "takeover", "enabled")
    filter_horizontal = ("screens",)
    actions = ("end_now",)
    change_list_template = "admin/signage/announcement_change_list.html"
    fieldsets = (
        (None, {"fields": (("text_hu", "text_en"), ("level", "takeover"), "enabled")}),
        (_("Window"), {"fields": (("starts_at", "ends_at"), "screens", "template")}),
    )

    @admin.display(boolean=True, description=_("Active"))
    def active_now(self, obj):
        return obj.is_active()

    @admin.action(description=_("End now"))
    def end_now(self, request, queryset):
        queryset.update(ends_at=timezone.now())

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        custom = [
            path(
                "from-template/",
                self.admin_site.admin_view(self.from_template_view),
                name="signage_announcement_from_template",
            )
        ]
        return [*custom, *super().get_urls()]

    def from_template_view(self, request):
        template = None
        template_id = request.POST.get("template") or request.GET.get("template")
        if template_id:
            template = AnnouncementTemplate.objects.filter(pk=template_id).first()
        placeholders = template.placeholders if template else ()
        form = AnnouncementFromTemplateForm(
            request.POST or None, placeholders=placeholders, initial={"template": template}
        )
        if request.method == "POST" and "create" in request.POST and form.is_valid():
            values = {name: form.cleaned_data[f"ph_{name}"] for name in placeholders}
            text_hu = template.text_hu.format(**values)
            text_en = template.text_en.format(**values)
            minutes = int(form.cleaned_data["duration_minutes"])
            now = timezone.now()
            announcement = Announcement.objects.create(
                text_hu=text_hu,
                text_en=text_en,
                level=template.level,
                takeover=template.takeover,
                starts_at=now,
                ends_at=now + timezone.timedelta(minutes=minutes) if minutes else None,
                template=template,
                created_by=request.user,
            )
            announcement.screens.set(form.cleaned_data["screens"])
            messages.success(request, _("Announcement is live."))
            return redirect("admin:signage_announcement_changelist")
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "template": template,
            "opts": self.model._meta,
            "title": _("New announcement from a template"),
        }
        return TemplateResponse(request, "admin/signage/announcement_from_template.html", context)


INTEGRATION_FIELDS = (
    "kind",
    "enabled",
    "base_url",
    "auth_type",
    "username",
    "password",
    "token",
    "header_name",
    "verify_tls",
    "ca_bundle",
    "connect_timeout",
    "read_timeout",
    "cache_seconds",
    "tournament_id",
    "mirror_announcement",
)


class IntegrationForm(forms.ModelForm):
    class Meta:
        model = Integration
        fields = INTEGRATION_FIELDS
        widgets: ClassVar[dict] = {
            "password": forms.PasswordInput(render_value=True),
            "token": forms.PasswordInput(render_value=True),
        }


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):
    form = IntegrationForm
    list_display = ("kind", "enabled", "base_url", "auth_type", "cache_seconds", "freshness")
    list_editable = ("enabled",)
    fieldsets = (
        (None, {"fields": ("kind", "enabled", "base_url")}),
        (
            _("Authentication"),
            {"fields": ("auth_type", ("username", "password"), ("token", "header_name"))},
        ),
        (
            _("Connection"),
            {
                "fields": (
                    ("verify_tls", "ca_bundle"),
                    ("connect_timeout", "read_timeout"),
                    "cache_seconds",
                )
            },
        ),
        (_("Options"), {"fields": ("tournament_id", "mirror_announcement")}),
    )

    def get_readonly_fields(self, request, obj=None):
        return ("kind",) if obj else ()

    def has_add_permission(self, request):
        return Integration.objects.count() < len(Integration.Kind)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Last fetch"))
    def freshness(self, obj):
        client = {
            "projectile": ProjectileClient,
            "bracket": BracketClient,
            "streams": StreamsClient,
        }[obj.kind](obj)
        status = client.status()
        if not status["enabled"]:
            return _("disabled")
        if status["last_fetch"] is None:
            return _("never")
        return timezone.localtime(status["last_fetch"]).strftime("%H:%M:%S") + (
            "" if status["fresh"] else _(" (stale)")
        )


@staff_member_required
def overview(request):
    """One page for the organizer desk: phase, screens with previews, integrations, warnings."""
    event = Event.get_solo()
    now = timezone.now()
    screens = []
    for screen in Screen.objects.filter(enabled=True):
        bundle = build_bundle(screen, now)
        screens.append(
            {
                "screen": screen,
                "url": reverse("signage:display", kwargs={"slug": screen.slug}),
                "passes": len(bundle["passes"]),
                "warnings": bundle["warnings"],
                "announcement": bundle["announcement"],
            }
        )
    integrations = [
        {"projectile": ProjectileClient, "bracket": BracketClient, "streams": StreamsClient}[
            row.kind
        ](row).status()
        for row in Integration.objects.all()
    ]
    context = {
        **admin.site.each_context(request),
        "title": _("Signage overview"),
        "event": event,
        "phase": resolve_phase(event, now),
        "phases": Phase.objects.order_by("order"),
        "screens": screens,
        "integrations": integrations,
    }
    return render(request, "admin/signage/overview.html", context)


_original_get_urls = admin.site.get_urls


def _get_urls():
    return [path("signage/overview/", overview, name="signage_overview"), *_original_get_urls()]


admin.site.get_urls = _get_urls
