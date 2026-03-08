from django.urls import path

from . import views

app_name = "impose"

urlpatterns = [
    path("", views.TemplateListView.as_view(), name="list"),
    path("new/", views.TemplateCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.TemplateEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.TemplateDeleteView.as_view(), name="delete"),
]
