from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("qr/", views.qr_page, name="qr_page"),
    path("qr/image/", views.qr_image, name="qr_image"),
    path("links/", views.links_page, name="links"),
    path("downloads/printer-driver/<str:platform>/", views.printer_driver_download, name="printer_driver_download"),
]
