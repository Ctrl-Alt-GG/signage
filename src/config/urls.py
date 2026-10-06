from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from health_check.views import HealthCheckView
from rest_framework.permissions import IsAdminUser

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("signage.api.urls")),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=(IsAdminUser,)),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=(IsAdminUser,)),
        name="api-docs",
    ),
    path(
        "health/",
        HealthCheckView.as_view(
            checks=("health_check.checks.Cache", "health_check.checks.Database")
        ),
        name="health",
    ),
    # The display itself is the frontend container; the backend root goes to the admin.
    path("", RedirectView.as_view(pattern_name="admin:index", permanent=False), name="root"),
]

if settings.DEBUG and not settings.STORAGE.enabled:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
