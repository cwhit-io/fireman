from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("qr/", views.qr_page, name="qr_page"),
    path("qr/image/", views.qr_image, name="qr_image"),
]
