from django.urls import path

from . import views

app_name = "routing"

urlpatterns = [
    path("", views.PresetListView.as_view(), name="list"),
    path("new/", views.PresetCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.PresetEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.PresetDeleteView.as_view(), name="delete"),
    path(
        "<int:pk>/test-connection/",
        views.PresetTestConnectionView.as_view(),
        name="test_connection",
    ),
]
