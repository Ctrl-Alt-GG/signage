from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig


class SignageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "signage"
    verbose_name = "Signage"


class SignageAdminConfig(AdminConfig):
    default_site = "signage.sites.SignageAdminSite"
