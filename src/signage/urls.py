from django.urls import path

from signage import views

app_name = "signage"

urlpatterns = [
    path("", views.display_root, name="root"),
    path("display/", views.display_root, name="display-root"),
    path("display/<slug:slug>/", views.display, name="display"),
]
