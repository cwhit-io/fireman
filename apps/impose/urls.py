from django.urls import path

from . import views

app_name = "impose"

urlpatterns = [
    path("", views.TemplateListView.as_view(), name="list"),
    path("new/", views.TemplateCreateView.as_view(), name="create"),
    path("export-all/", views.TemplateExportAllView.as_view(), name="export_all"),
    path("import/", views.TemplateImportView.as_view(), name="import"),
    path("<int:pk>/edit/", views.TemplateEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.TemplateDeleteView.as_view(), name="delete"),
    path("<int:pk>/export/", views.TemplateExportView.as_view(), name="export"),
    path("presets/", views.PresetsView.as_view(), name="presets"),
]
