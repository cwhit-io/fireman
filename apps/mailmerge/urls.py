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
    path("<uuid:pk>/edit/", views.MailMergeJobEditView.as_view(), name="edit"),
    path(
        "<uuid:pk>/artwork/",
        views.MailMergeJobArtworkServeView.as_view(),
        name="serve_artwork",
    ),
    path("<uuid:pk>/delete/", views.MailMergeJobDeleteView.as_view(), name="delete"),
    path(
        "<uuid:pk>/download/",
        views.MailMergeJobDownloadView.as_view(),
        name="download",
    ),
    path(
        "<uuid:pk>/download/gangup/",
        views.MailMergeJobDownloadGangupView.as_view(),
        name="download_gangup",
    ),
    path(
        "<uuid:pk>/download/addresses/",
        views.MailMergeJobDownloadAddressPdfView.as_view(),
        name="download_addresses",
    ),
    path(
        "<uuid:pk>/generate-merged/",
        views.MailMergeGenerateMergedView.as_view(),
        name="generate_merged",
    ),
    path(
        "<uuid:pk>/records/",
        views.MailMergeJobRecordsView.as_view(),
        name="records",
    ),
    path(
        "address-block/",
        views.AddressBlockConfigView.as_view(),
        name="address_block_config",
    ),
    path(
        "<uuid:pk>/send-gangup/",
        views.MailMergeJobSendGangupToFieryView.as_view(),
        name="send_gangup_to_fiery",
    ),
    path(
        "<uuid:pk>/send-addresses/",
        views.MailMergeJobSendAddressesToFieryView.as_view(),
        name="send_addresses_to_fiery",
    ),
]
