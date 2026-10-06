from django.urls import path

from signage.api import views

app_name = "signage-api"

urlpatterns = [
    path("screens/", views.ScreenListView.as_view(), name="screens"),
    path("screens/<slug:slug>/bundle/", views.BundleView.as_view(), name="bundle"),
    path("schedule/", views.ScheduleView.as_view(), name="schedule"),
    path("phase/", views.PhaseView.as_view(), name="phase"),
    path("announcements/active/", views.ActiveAnnouncementsView.as_view(), name="announcements"),
    path("display/background.svg", views.background, name="background"),
    path("display/thumbnails/<str:stream_id>/", views.thumbnail, name="thumbnail"),
]
