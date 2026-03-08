from django.urls import path

from . import views

app_name = "rules"

urlpatterns = [
    path("", views.RuleListView.as_view(), name="list"),
    path("new/", views.RuleCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.RuleEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.RuleDeleteView.as_view(), name="delete"),
    path("<int:pk>/toggle/", views.RuleToggleView.as_view(), name="toggle"),
]
