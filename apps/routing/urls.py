from django.urls import path
from django.views.generic.base import RedirectView

from . import views

app_name = "routing"

urlpatterns = [
    path("", RedirectView.as_view(url="/", permanent=False), name="list"),
    path("new/", RedirectView.as_view(url="/", permanent=False), name="create"),
    path("<int:pk>/edit/", RedirectView.as_view(url="/", permanent=False), name="edit"),
    path(
        "<int:pk>/delete/",
        RedirectView.as_view(url="/", permanent=False),
        name="delete",
    ),
    path(
        "<int:pk>/test-connection/",
        views.PresetTestConnectionView.as_view(),
        name="test_connection",
    ),
    path(
        "<int:pk>/duplicate/",
        views.PresetDuplicateView.as_view(),
        name="duplicate",
    ),
]
