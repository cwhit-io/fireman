from django.urls import path
from django.views.generic.base import RedirectView

app_name = "impose"

urlpatterns = [
    path("", RedirectView.as_view(url="/", permanent=False), name="list"),
    path("new/", RedirectView.as_view(url="/", permanent=False), name="create"),
    path(
        "export-all/", RedirectView.as_view(url="/", permanent=False), name="export_all"
    ),
    path("import/", RedirectView.as_view(url="/", permanent=False), name="import"),
    path("<int:pk>/edit/", RedirectView.as_view(url="/", permanent=False), name="edit"),
    path(
        "<int:pk>/delete/",
        RedirectView.as_view(url="/", permanent=False),
        name="delete",
    ),
    path(
        "<int:pk>/export/",
        RedirectView.as_view(url="/", permanent=False),
        name="export",
    ),
    path("presets/", RedirectView.as_view(url="/", permanent=False), name="presets"),
]
