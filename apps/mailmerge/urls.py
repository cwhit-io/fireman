from django.urls import path

from . import views

app_name = "mailmerge"

urlpatterns = [
    path("", views.MailMergeJobListView.as_view(), name="list"),
    path("upload/", views.MailMergeJobUploadView.as_view(), name="upload"),
    path("sample-csv/", views.MailMergeSampleCsvView.as_view(), name="sample_csv"),
    path("new-movers-csv/", views.NewMoversCsvView.as_view(), name="new_movers_csv"),
    path("pco-lists/", views.PcoListsJsonView.as_view(), name="pco_lists"),
    path("pco-csv/", views.PcoCsvView.as_view(), name="pco_csv"),
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
        "<uuid:pk>/download/addresses/print-preview/",
        views.MailMergeJobDownloadAddressesPrintPreviewView.as_view(),
        name="download_addresses_print_preview",
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
        "<uuid:pk>/send-gangup/",
        views.MailMergeJobSendGangupToFieryView.as_view(),
        name="send_gangup_to_fiery",
    ),
    path(
        "<uuid:pk>/send-addresses/",
        views.MailMergeJobSendAddressesToFieryView.as_view(),
        name="send_addresses_to_fiery",
    ),
    path(
        "<uuid:pk>/replace-csv/",
        views.MailMergeJobReplaceCsvView.as_view(),
        name="replace_csv",
    ),
]
