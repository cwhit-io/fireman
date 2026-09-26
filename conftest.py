import pytest

TEST_PRINTOPS_API_TOKEN = "test-printops-token"


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    """Keep tests off the real media disk so job files are never deleted."""
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture(autouse=True)
def printops_api_token(settings):
    """Deterministic bearer token for Ninja /api tests (not the live secret)."""
    settings.PRINTOPS_API_TOKEN = TEST_PRINTOPS_API_TOKEN


@pytest.fixture
def api_auth_headers():
    return {"HTTP_AUTHORIZATION": f"Bearer {TEST_PRINTOPS_API_TOKEN}"}


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
