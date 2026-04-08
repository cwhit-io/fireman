from django.urls import path

from . import views

app_name = "qr"

urlpatterns = [
    path("", views.QRCodeGeneratorView.as_view(), name="generator"),
    path("preview/", views.QRCodePreviewView.as_view(), name="preview"),
    path("download/", views.QRCodeDownloadView.as_view(), name="download"),
]
