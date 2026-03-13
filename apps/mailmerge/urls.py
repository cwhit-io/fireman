from django.urls import path

from . import views

app_name = "mailmerge"

urlpatterns = [
    path("", views.MailMergeJobListView.as_view(), name="list"),
    path("upload/", views.MailMergeJobUploadView.as_view(), name="upload"),
    path(
        "inspect-artwork/",
        views.MailMergeArtworkInspectView.as_view(),
        name="inspect_artwork",
    ),
    path("<uuid:pk>/", views.MailMergeJobDetailView.as_view(), name="detail"),
    path("<uuid:pk>/delete/", views.MailMergeJobDeleteView.as_view(), name="delete"),
    path(
        "<uuid:pk>/download/", views.MailMergeJobDownloadView.as_view(), name="download"
    ),
]