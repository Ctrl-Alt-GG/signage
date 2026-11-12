"""The Django admin is the only management UI. Everything organizers change at the event
is here: the event facts, the phase, slides, the schedule, announcements, screens, the
background artwork and the upstream connections."""

from __future__ import annotations

from datetime import timedelta
from decimal import DecimalException
from typing import ClassVar

import yaml
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.db.models import F
from django.db.models.functions import ExtractHour, ExtractMinute
from django.forms.models import BaseInlineFormSet
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from solo.admin import SingletonModelAdmin

from signage.content import lint
from signage.content import loader as content_loader
from signage.content.safe_yaml import load_yaml
from signage.integrations.bracket import BracketClient
from signage.integrations.projectile import ProjectileClient
from signage.integrations.streams import StreamsClient
from signage.links import display_url
from signage.models import (
    LANGS,
    Announcement,
    AnnouncementTemplate,
    DisplaySettings,
    Event,
    Game,
    Integration,
    Origin,
    Phase,
    RemovedSeed,
    ScheduleEntry,
    Screen,
    ScreenSlide,
    Slide,
    SlideItem,
)
from signage.rendering.bundle import build_bundle
from signage.rendering.phases import resolve_phase
from signage.rendering.placeholders import UNRESOLVED_MARKER

CLIENTS = {
    Integration.Kind.PROJECTILE: ProjectileClient,
    Integration.Kind.BRACKET: BracketClient,
    Integration.Kind.STREAMS: StreamsClient,
}

# About what the announcement bar shows in both languages at once. Beyond it the bar
# shows one language after the other, in smaller type.
BAR_COMFORTABLE_LENGTH = 110

admin.site.site_header = "Ctrl-Alt-GG Signage"
admin.site.site_title = "Signage admin"
admin.site.index_title = _("Signage administration")


class YamlImportForm(forms.Form):
    file = forms.FileField(label=_("YAML file"))
    overwrite = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Overwrite rows edited in the admin, and bring back rows deleted there"),
    )
    prune = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Remove seeded rows that are not in this file"),
        help_text=_(
            "Only for a complete file. Rows created or edited in the admin are never removed."
        ),
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        # The parser reads the whole file into memory, and more than that for a file
        # built to expand.
        if upload.size > settings.SIGNAGE_IMPORT_MAX_BYTES:
            raise ValidationError(_("The file is too large to be one of the content files."))
        return upload


class AdminOwnedMixin:
    """What an organizer does here is theirs. A row saved here carries the admin origin, so
    a later YAML import leaves it alone. A row deleted here is remembered as deleted, so
    the import that runs on every start does not bring it back."""

    def save_model(self, request, obj, form, change):
        obj.origin = Origin.ADMIN
        if not change:
            RemovedSeed.forget(type(obj), obj.seed_key)
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        RemovedSeed.remember(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for row in queryset:
            RemovedSeed.remember(row)
        super().delete_queryset(request, queryset)


class YamlImportMixin:
    """Adds an "Import from YAML" button and view to a model admin. Subclasses set
    `yaml_loader` to a function taking the parsed document and returning a Report, and
    `yaml_linter` to the content lint for that file, which runs before anything is saved."""

    yaml_loader = None
    yaml_linter = None
    yaml_name = ""
    change_list_template = "admin/signage/change_list_with_import.html"

    def can_import(self, request) -> bool:
        """An import creates rows and replaces them, so it takes the rights to do both."""
        return self.has_add_permission(request) and self.has_change_permission(request)

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
        if self.can_import(request):
            info = self.model._meta.app_label, self.model._meta.model_name
            extra_context["import_yaml_url"] = reverse("admin:{}_{}_import_yaml".format(*info))
            extra_context["import_yaml_name"] = self.yaml_name
        return super().changelist_view(request, extra_context=extra_context)

    def import_yaml_view(self, request):
        if not self.can_import(request):
            raise PermissionDenied
        form = YamlImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            if form.cleaned_data["prune"] and not self.has_delete_permission(request):
                raise PermissionDenied
            upload = form.cleaned_data["file"]
            try:
                text = upload.read().decode("utf-8")
                lint.lint_text(text, upload.name)
                data = load_yaml(text) or {}
                if not isinstance(data, dict):
                    raise lint.LintError(_("the top level must be a mapping"))
                self.lint_yaml(data)
                report = self.run_yaml_loader(
                    data, overwrite=form.cleaned_data["overwrite"], prune=form.cleaned_data["prune"]
                )
            except (
                lint.LintError,
                yaml.YAMLError,
                ValidationError,
                UnicodeDecodeError,
                # A file of another shape than the lint expects, and what the database
                # refuses. The loaders run in a transaction, so nothing is half saved.
                AttributeError,
                KeyError,
                TypeError,
                ValueError,
                DecimalException,
                DatabaseError,
            ) as error:
                form.add_error("file", _("Import failed: %(error)s") % {"error": error})
            else:
                messages.success(request, report.summary())
                for item in report.removed:
                    messages.warning(request, _("Removed %(item)s") % {"item": item})
                for item in report.skipped:
                    messages.warning(request, _("Skipped %(item)s") % {"item": item})
                for warning in report.warnings:
                    messages.warning(request, warning)
                info = self.model._meta.app_label, self.model._meta.model_name
                return redirect("admin:{}_{}_changelist".format(*info))
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "opts": self.model._meta,
            "title": _("Import %(name)s from YAML") % {"name": self.yaml_name},
        }
        return TemplateResponse(request, "admin/signage/import_yaml.html", context)

    def run_yaml_loader(self, data, *, overwrite, prune):
        return type(self).yaml_loader(data, overwrite=overwrite, prune=prune)

    def lint_yaml(self, data):
        linter = type(self).yaml_linter
        if linter is not None:
            linter(data)


def _slides_linter(data):
    lint.lint_slides(data, Phase.objects.values_list("key", flat=True))


def _schedule_linter(data):
    lint.lint_schedule(data, Game.objects.values_list("slug", flat=True))


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ("wifi_ssid", "wifi_password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("wifi_ssid", "wifi_password"):
            if name in self.fields:
                self.fields[name].strip = False


@admin.register(Event)
class EventAdmin(YamlImportMixin, SingletonModelAdmin):
    form = EventForm
    yaml_loader = staticmethod(content_loader.load_event)
    yaml_linter = staticmethod(lint.lint_event)
    yaml_name = "event.yaml"
    change_list_template = None
    change_form_template = "admin/signage/event_change_form.html"
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

    def can_import(self, request) -> bool:
        # There is one event, which is changed and never added. Its file also holds the
        # phases, which the import creates and replaces.
        return self.has_change_permission(request) and request.user.has_perms(
            ("signage.add_phase", "signage.change_phase", "signage.delete_phase")
        )

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        custom = [
            path(
                "set-phase/<slug:key>/",
                self.admin_site.admin_view(self.set_phase_view),
                name="{}_{}_set_phase".format(*info),
            ),
        ]
        return [*custom, *super().get_urls()]

    def set_phase_view(self, request, key: str):
        if not self.has_change_permission(request):
            raise PermissionDenied
        phase = Phase.objects.filter(key=key).first()
        if request.method == "POST" and phase:
            event = Event.get_solo()
            event.phase_mode = Event.PhaseMode.MANUAL
            event.current_phase = phase
            event.save(update_fields=["phase_mode", "current_phase"])
            messages.success(request, _("Phase set to %(key)s") % {"key": key})
        return redirect("admin:signage_event_change")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if self.has_change_permission(request):
            extra_context["phases"] = Phase.objects.order_by("order")
        if self.can_import(request):
            extra_context["import_yaml_url"] = reverse("admin:signage_event_import_yaml")
        return super().change_view(request, object_id, form_url, extra_context=extra_context)


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
        url = reverse("signage-api:background") + f"?v={obj.background_version}"
        return format_html(
            '<img src="{}" alt="" style="max-width:480px;border:1px solid #444;border-radius:8px">',
            url,
        )


@admin.register(Phase)
class PhaseAdmin(AdminOwnedMixin, admin.ModelAdmin):
    list_display = ("key", "name_hu", "name_en", "starts", "day_offset", "order", "origin")
    list_editable = ("starts", "day_offset", "order")
    readonly_fields = ("origin",)
    ordering = ("order",)


@admin.register(Game)
class GameAdmin(AdminOwnedMixin, YamlImportMixin, admin.ModelAdmin):
    yaml_loader = staticmethod(content_loader.load_games)
    yaml_linter = staticmethod(lint.lint_games)
    yaml_name = "games.yaml"
    list_display = ("name", "slug", "short", "hosted", "tournament", "swatch", "origin")
    readonly_fields = ("origin",)
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
class ScheduleEntryAdmin(AdminOwnedMixin, YamlImportMixin, admin.ModelAdmin):
    yaml_loader = staticmethod(content_loader.load_schedule)
    yaml_linter = staticmethod(_schedule_linter)
    yaml_name = "schedule.yaml"
    list_display = ("local_start", "type", "label", "title_hu", "title_en", "game", "origin")
    list_editable = ("type",)
    list_filter = ("type", "day_offset", "game")
    search_fields = ("key", "title_hu", "title_en", "label")
    ordering = ("day_offset", "time", "order")
    readonly_fields = ("origin",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    ("time", "day_offset"),
                    "type",
                    ("game", "label"),
                    "order",
                    "key",
                    "origin",
                )
            },
        ),
        (_("Text"), {"fields": (("title_hu", "title_en"), ("note_hu", "note_en"))}),
    )

    def get_queryset(self, request):
        # Minutes since the start of the first day, which is the order the entries happen
        # in. Sorting the column by the time alone would put 01:00 after midnight first.
        minutes = F("day_offset") * 1440 + ExtractHour("time") * 60 + ExtractMinute("time")
        return super().get_queryset(request).annotate(happens_at=minutes)

    @admin.display(description=_("Starts"), ordering="happens_at")
    def local_start(self, obj):
        return date_format(obj.starts_at(Event.get_solo()), "D H:i")


class SlideItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        counts: dict[int, int] = {}
        for form in self.forms:
            data = getattr(form, "cleaned_data", None)
            if not data or data.get("DELETE"):
                continue
            column = data.get("column") or 1
            counts[column] = counts.get(column, 0) + 1
        # The layouts show this many and would drop the rest without a word.
        maximum = (
            lint.MAX_SPLIT_ITEMS if self.instance.layout == Slide.Layout.SPLIT else lint.MAX_ITEMS
        )
        if any(count > maximum for count in counts.values()):
            raise ValidationError(
                _("A slide shows at most %(max)d items per column. Move the rest to another slide.")
                % {"max": maximum}
            )


class SlideItemInline(admin.TabularInline):
    model = SlideItem
    formset = SlideItemFormSet
    extra = 0
    fields = ("column", "order", "text_hu", "text_en", "icon")
    ordering = ("column", "order")


class ScreenSlideInline(admin.TabularInline):
    model = ScreenSlide
    extra = 0
    autocomplete_fields = ("slide",)
    ordering = ("order",)


@admin.register(Slide)
class SlideAdmin(AdminOwnedMixin, YamlImportMixin, admin.ModelAdmin):
    yaml_loader = staticmethod(content_loader.load_slides)
    yaml_linter = staticmethod(_slides_linter)
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
                "description": _(
                    "Names in braces are filled in from the event: %(names)s. A slide with a "
                    "value that is not set yet stays off the screens."
                )
                % {"names": ", ".join(f"{{{name}}}" for name in lint.EVENT_PLACEHOLDERS)},
                "fields": (
                    ("kicker_hu", "kicker_en"),
                    ("title_hu", "title_en"),
                    ("body_hu", "body_en"),
                    ("footer_hu", "footer_en"),
                    ("empty_hu", "empty_en"),
                ),
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

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("phases")

    @admin.display(description=_("Phases"))
    def phase_list(self, obj):
        return "all" if obj.all_phases else ", ".join(p.key for p in obj.phases.all())

    @admin.display(description=_("Preview"))
    def preview_links(self, obj):
        screen = DisplaySettings.get_solo().default_screen_slug
        base = display_url(screen)
        return format_html(
            '<a href="{}?preview={}&lang=hu" target="_blank">HU</a> | '
            '<a href="{}?preview={}&lang=en" target="_blank">EN</a>',
            base,
            obj.key,
            base,
            obj.key,
        )

    # Both are an organizer's decision about the slide, like ticking the box in the list,
    # so the slide becomes theirs and a later import does not turn it back.
    @admin.action(description=_("Enable selected slides"), permissions=["change"])
    def enable_slides(self, request, queryset):
        queryset.update(enabled=True, origin=Origin.ADMIN)

    @admin.action(description=_("Disable selected slides"), permissions=["change"])
    def disable_slides(self, request, queryset):
        queryset.update(enabled=False, origin=Origin.ADMIN)


@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "enabled", "refresh_seconds", "language_mode", "open_link")
    list_editable = ("enabled", "refresh_seconds", "language_mode")
    inlines = (ScreenSlideInline,)
    prepopulated_fields: ClassVar[dict] = {"slug": ("name",)}

    @admin.display(description=_("Display"))
    def open_link(self, obj):
        url = display_url(obj.slug)
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)


@admin.register(AnnouncementTemplate)
class AnnouncementTemplateAdmin(AdminOwnedMixin, YamlImportMixin, admin.ModelAdmin):
    yaml_loader = staticmethod(content_loader.load_announcements)
    yaml_linter = staticmethod(lint.lint_announcements)
    yaml_name = "announcements.yaml"
    list_display = ("key", "level", "takeover", "text_hu", "placeholder_list", "origin")
    readonly_fields = ("origin",)
    list_filter = ("level", "takeover")

    @admin.display(description=_("Placeholders"))
    def placeholder_list(self, obj):
        return ", ".join(obj.placeholders) or "-"


@admin.register(RemovedSeed)
class RemovedSeedAdmin(admin.ModelAdmin):
    """The seeded rows that were deleted here. Deleting an entry lets the next import
    bring its row back."""

    list_display = ("model", "key", "removed_at")
    list_filter = ("model",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class AnnouncementFromTemplateForm(forms.Form):
    duration_minutes = forms.TypedChoiceField(
        label=_("Show it for"),
        coerce=int,
        choices=(
            (10, _("10 minutes")),
            (30, _("30 minutes")),
            (60, _("60 minutes")),
            (0, _("until ended in the list")),
        ),
        initial=10,
    )
    screens = forms.ModelMultipleChoiceField(
        queryset=Screen.objects.filter(enabled=True),
        required=False,
        help_text=_("Leave empty for every screen."),
    )

    def __init__(self, *args, placeholders=(), **kwargs):
        super().__init__(*args, **kwargs)
        # The values come first: they are what the organizer is here to type.
        fields = {
            f"ph_{name}": forms.CharField(label=f"{{{name}}}", max_length=120)
            for name in placeholders
        }
        self.fields = {**fields, **self.fields}

    def values(self, placeholders) -> dict[str, str]:
        return {name: self.cleaned_data[f"ph_{name}"] for name in placeholders}


def _usable(value: str | None) -> bool:
    return bool(value and value.strip() and UNRESOLVED_MARKER not in value)


def _length_note(text: str, takeover: bool) -> str:
    if takeover or len(text) <= BAR_COMFORTABLE_LENGTH:
        return ""
    return _(
        "Long for the bar: it will show one language after the other in smaller type. "
        "A takeover template suits a text of this length better."
    )


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

    @admin.action(description=_("End now"), permissions=["change"])
    def end_now(self, request, queryset):
        queryset.update(ends_at=timezone.now())

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        for lang in LANGS:
            if note := _length_note(obj.text("text", lang), obj.takeover):
                messages.warning(request, f"{lang.upper()}: {note}")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["can_publish"] = self.has_add_permission(request)
        return super().changelist_view(request, extra_context=extra_context)

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
        """Publish an announcement from a template in two steps: choose the template, then
        fill in what it asks for, look at the text as the screens will show it, and publish.

        Choosing is a link, so the second step starts with an empty form and nothing in it
        is marked as wrong before the organizer has typed anything."""
        if not self.has_add_permission(request):
            raise PermissionDenied
        raw_id = request.POST.get("template") or request.GET.get("template") or ""
        try:
            template_id = forms.IntegerField(min_value=1, max_value=2**63 - 1).clean(raw_id)
        except ValidationError:
            template = None
        else:
            template = AnnouncementTemplate.objects.filter(pk=template_id).first()
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("New announcement from a template"),
            "template": template,
        }
        if template is None:
            context["templates"] = AnnouncementTemplate.objects.all()
            return TemplateResponse(
                request, "admin/signage/announcement_from_template.html", context
            )

        # What the event already knows is filled in, in each language. The organizer is
        # asked for the rest.
        event = Event.get_solo()
        known = {lang: event.placeholder_values(lang) for lang in LANGS}
        from_event = [
            name
            for name in template.placeholders
            if all(_usable(known[lang].get(name)) for lang in LANGS)
        ]
        asked = [name for name in template.placeholders if name not in from_event]
        form = AnnouncementFromTemplateForm(
            request.POST if request.method == "POST" else None, placeholders=asked
        )
        preview = None
        if request.method == "POST" and form.is_valid():
            typed = form.values(asked)
            now = timezone.now()
            minutes = form.cleaned_data["duration_minutes"]
            announcement = Announcement(
                level=template.level,
                takeover=template.takeover,
                starts_at=now,
                ends_at=now + timedelta(minutes=minutes) if minutes else None,
                template=template,
                created_by=request.user,
            )
            for lang in LANGS:
                values = {**{name: known[lang][name] for name in from_event}, **typed}
                text = lint.PLACEHOLDER_RE.sub(
                    lambda match, values=values: values.get(match.group(1), match.group(0)),
                    template.text("text", lang),
                )
                setattr(announcement, f"text_{lang}", text)
            try:
                announcement.full_clean()
            except ValidationError as error:
                # The texts are not fields of this form: they are made from the template
                # and what was typed. So the form as a whole says which one is wrong.
                labels = {"text_hu": "HU", "text_en": "EN"}
                for field, problems in error.message_dict.items():
                    for problem in problems:
                        form.add_error(None, f"{labels.get(field, field)}: {problem}")
            else:
                if "publish" in request.POST:
                    announcement.save()
                    announcement.screens.set(form.cleaned_data["screens"])
                    messages.success(request, _("Announcement is live."))
                    return redirect("admin:signage_announcement_changelist")
                preview = [
                    {
                        "lang": lang.upper(),
                        "text": announcement.text("text", lang),
                        "length": len(announcement.text("text", lang)),
                        "note": _length_note(announcement.text("text", lang), template.takeover),
                    }
                    for lang in LANGS
                ]
        context.update(
            form=form,
            preview=preview,
            from_event=[
                {"name": name, "values": [known[lang][name] for lang in LANGS]}
                for name in from_event
            ],
        )
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
SECRET_FIELDS = ("password", "token")


class SecretInput(forms.PasswordInput):
    """A field for a stored secret. The stored value is never written into the page, where
    anyone looking at the screen or its source could read it; what is typed replaces it.
    `new-password` keeps the browser from offering the organizer's own login here, which
    saving would store as the upstream's."""

    def __init__(self):
        super().__init__(render_value=False, attrs={"autocomplete": "new-password"})


class IntegrationForm(forms.ModelForm):
    class Meta:
        model = Integration
        fields = INTEGRATION_FIELDS
        widgets: ClassVar[dict] = {
            "username": forms.TextInput(attrs={"autocomplete": "off"}),
            "password": SecretInput(),
            "token": SecretInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in SECRET_FIELDS:
            if name in self.fields and getattr(self.instance, name):
                self.fields[name].help_text = _(
                    "A value is stored. Leave this empty to keep it, or type a new one."
                )

    def clean(self):
        cleaned = super().clean()
        for name in SECRET_FIELDS:
            # Empty means "as it was", so that saving another field keeps the secret.
            if name in cleaned and not cleaned[name]:
                cleaned[name] = getattr(self.instance, name)
        return cleaned


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

    def get_fieldsets(self, request, obj=None):
        if self.has_change_permission(request, obj):
            return self.fieldsets
        # Someone who may only look sees every field as text. Not the secrets: for those
        # they see whether one is set.
        states = {"password": "password_state", "token": "token_state"}

        def without_secrets(fields):
            return tuple(
                without_secrets(field) if isinstance(field, tuple) else states.get(field, field)
                for field in fields
            )

        return tuple(
            (name, {**options, "fields": without_secrets(options["fields"])})
            for name, options in self.fieldsets
        )

    def get_readonly_fields(self, request, obj=None):
        return ("kind", "password_state", "token_state") if obj else ()

    @admin.display(description=_("Password"))
    def password_state(self, obj):
        return _("set") if obj.password else _("not set")

    @admin.display(description=_("Token"))
    def token_state(self, obj):
        return _("set") if obj.token else _("not set")

    def has_add_permission(self, request):
        return Integration.objects.count() < len(Integration.Kind)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Last fetch"))
    def freshness(self, obj):
        status = CLIENTS[obj.kind](obj).status()
        if not obj.enabled:
            return _("disabled")
        if not status["enabled"]:
            return _("not configured")
        if status["last_fetch"] is None:
            return status["error"] or _("never")
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
                "url": display_url(screen.slug),
                "passes": len(bundle["passes"]),
                "warnings": bundle["warnings"],
                "announcements": bundle["announcements"],
            }
        )
    integrations = [CLIENTS[row.kind](row).status() for row in Integration.objects.all()]
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
