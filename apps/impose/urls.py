from django.urls import path
from django.views.generic.base import RedirectView

from . import views

app_name = "impose"

urlpatterns = [
    path("", views.print_templates, name="print_templates"),
    path("<int:pk>/download/<str:orientation>/", views.print_size_template_pdf, name="template_pdf"),
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
