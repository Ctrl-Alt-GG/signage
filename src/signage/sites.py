"""The admin site. The organizer overview is one of its pages, linked from the index."""

from django.contrib import admin
from django.urls import path
from django.utils.translation import gettext_lazy as _


class SignageAdminSite(admin.AdminSite):
    site_header = "Ctrl-Alt-GG Signage"
    site_title = "Signage admin"
    index_title = _("Signage administration")
    index_template = "admin/signage/index.html"

    def get_urls(self):
        # The views live with the model admins, which register on this site.
        from signage.admin import overview

        return [
            path("signage/overview/", self.admin_view(overview), name="signage_overview"),
            *super().get_urls(),
        ]
