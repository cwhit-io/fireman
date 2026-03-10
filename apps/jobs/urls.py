from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.JobListView.as_view(), name="list"),
    path("upload/", views.JobUploadView.as_view(), name="upload"),
    path(
        "upload/templates/",
        views.JobUploadTemplatesView.as_view(),
        name="upload_templates",
    ),
    path("<uuid:pk>/", views.JobDetailView.as_view(), name="detail"),
    path(
        "<uuid:pk>/apply-template/",
        views.JobApplyTemplateView.as_view(),
        name="apply_template",
    ),
    path("<uuid:pk>/delete/", views.JobDeleteView.as_view(), name="delete"),
    path("<uuid:pk>/preview/", views.JobPreviewView.as_view(), name="preview"),
    path(
        "<uuid:pk>/source-preview/",
        views.JobSourcePreviewView.as_view(),
        name="source_preview",
    ),
    path("<uuid:pk>/download/", views.JobDownloadView.as_view(), name="download"),
    path("<uuid:pk>/resend/", views.JobResendView.as_view(), name="resend"),
    path(
        "<uuid:pk>/toggle-save/", views.JobToggleSaveView.as_view(), name="toggle_save"
    ),
    path("<uuid:pk>/rename/", views.JobRenameView.as_view(), name="rename"),
    path("<uuid:pk>/calc-sheets/", views.calc_sheets, name="calc_sheets"),
    path(
        "<uuid:pk>/preflight-acknowledge/",
        views.JobPreflightAcknowledgeView.as_view(),
        name="preflight_acknowledge",
    ),
]
