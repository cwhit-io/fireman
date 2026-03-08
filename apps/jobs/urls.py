from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.JobListView.as_view(), name="list"),
    path("upload/", views.JobUploadView.as_view(), name="upload"),
    path("<uuid:pk>/", views.JobDetailView.as_view(), name="detail"),
    path(
        "<uuid:pk>/apply-ruleset/",
        views.JobApplyRulesetView.as_view(),
        name="apply_ruleset",
    ),
    path("<uuid:pk>/delete/", views.JobDeleteView.as_view(), name="delete"),
    path("<uuid:pk>/preview/", views.JobPreviewView.as_view(), name="preview"),
    path("<uuid:pk>/download/", views.JobDownloadView.as_view(), name="download"),
    path("<uuid:pk>/resend/", views.JobResendView.as_view(), name="resend"),
]
