from django.urls import path
from django.views.generic.base import RedirectView

from . import views

app_name = "cutter"

urlpatterns = [
    path("", RedirectView.as_view(url="/", permanent=False), name="list"),
    path("new/", RedirectView.as_view(url="/", permanent=False), name="create"),
    path("<int:pk>/edit/", RedirectView.as_view(url="/", permanent=False), name="edit"),
    path(
        "<int:pk>/delete/",
        RedirectView.as_view(url="/", permanent=False),
        name="delete",
    ),
    path("<int:pk>/barcode.png", views.ProgramBarcodeView.as_view(), name="barcode"),
]
