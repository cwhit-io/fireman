import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestIndexView:
    def test_index_returns_200(self, client: Client):
        response = client.get(reverse("core:index"))
        assert response.status_code == 200


class TestNinjaAPI:
    def test_hello_endpoint(self, client: Client):
        response = client.get("/api/hello")
        assert response.status_code == 200
        assert response.json()["message"] == "Hello from Django Ninja!"


class TestUserModel:
    def test_create_user(self, django_user_model):
        user = django_user_model.objects.create_user(
            username="alice", email="alice@example.com", password="pass"
        )
        assert user.pk is not None
        assert str(user) == "alice@example.com"

    def test_user_str_falls_back_to_username(self, django_user_model):
        user = django_user_model.objects.create_user(username="bob", password="pass")
        user.email = ""
        assert str(user) == "bob"
