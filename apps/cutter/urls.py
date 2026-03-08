from django.urls import path

from . import views

app_name = "cutter"

urlpatterns = [
    path("", views.ProgramListView.as_view(), name="list"),
    path("new/", views.ProgramCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.ProgramEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ProgramDeleteView.as_view(), name="delete"),
]
