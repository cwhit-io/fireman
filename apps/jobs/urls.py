from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.JobListView.as_view(), name="list"),
    path("upload/", views.JobUploadView.as_view(), name="upload"),
    path("<uuid:pk>/", views.JobDetailView.as_view(), name="detail"),
    path("<uuid:pk>/apply-ruleset/", views.JobApplyRulesetView.as_view(), name="apply_ruleset"),
]
