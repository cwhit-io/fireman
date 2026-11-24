from django.urls import path

from . import views

app_name = "brand_assets"

urlpatterns = [
    path("", views.brand_assets_page, name="index"),
    path("index.json", views.brand_assets_json, name="index_json"),
    path("llms.txt", views.brand_assets_llms_txt, name="llms_txt"),
    path("<int:pk>/download/", views.download_asset, name="download"),
]
