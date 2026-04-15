from django.urls import path

from . import views

app_name = "brand_assets"

urlpatterns = [
    path("", views.brand_assets_page, name="index"),
    path("<int:pk>/download/", views.download_asset, name="download"),
]
