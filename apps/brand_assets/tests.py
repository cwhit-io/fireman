import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .models import BrandAsset, BrandAssetCategory, BrandColor

pytestmark = pytest.mark.django_db

SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    b'<rect width="10" height="10" fill="#123456"/></svg>'
)


def _make_asset(name="Ember Logo", category=None, **kwargs):
    return BrandAsset.objects.create(
        name=name,
        category=category,
        svg_file=SimpleUploadedFile(f"{name}.svg", SVG, content_type="image/svg+xml"),
        **kwargs,
    )


class TestPublicAccess:
    def test_page_is_public(self, client):
        assert client.get(reverse("brand_assets:index")).status_code == 200

    def test_download_is_public(self, client):
        asset = _make_asset()
        url = reverse("brand_assets:download", args=[asset.pk])
        response = client.get(url, {"format": "svg", "variant": "color"})
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"


class TestBrandAssetsJson:
    def test_returns_json_index(self, client):
        category = BrandAssetCategory.objects.create(name="Logos", order=1)
        asset = _make_asset(category=category, description="Primary mark")
        BrandColor.objects.create(
            name="Ember Red", hex_value="#FF0000", cmyk_label="C:0 M:100 Y:100 K:0"
        )

        response = client.get(reverse("brand_assets:index_json"))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        payload = json.loads(response.content)
        assert payload["name"] == "Ember Brand Assets"
        assert payload["assets"][0]["name"] == asset.name
        assert payload["assets"][0]["category"] == "Logos"
        assert payload["assets"][0]["svg"].startswith("http://testserver/media/")
        assert payload["assets"][0]["downloads"]["svg"]["color"].startswith("http://")
        assert payload["colors"][0]["hex"] == "#FF0000"
        assert payload["colors"][0]["cmyk"] == "C:0 M:100 Y:100 K:0"

    def test_empty_index(self, client):
        response = client.get(reverse("brand_assets:index_json"))
        payload = json.loads(response.content)
        assert payload["assets"] == []
        assert payload["colors"] == []


class TestBrandAssetsLlmsTxt:
    def test_returns_plain_text(self, client):
        category = BrandAssetCategory.objects.create(name="Logos", order=1)
        _make_asset(category=category, description="Primary mark")
        BrandColor.objects.create(name="Ember Red", hex_value="#FF0000")

        response = client.get(reverse("brand_assets:llms_txt"))

        assert response.status_code == 200
        assert response["Content-Type"] == "text/plain; charset=utf-8"
        body = response.content.decode()
        assert body.startswith("# Ember Brand Assets")
        assert "Primary mark" in body
        assert "http://testserver/brand-assets/" in body
        assert "/brand-assets/index.json" in body
        assert "/download/?format=svg&variant=color" in body
        assert "Ember Red: #FF0000" in body

    def test_empty_state(self, client):
        response = client.get(reverse("brand_assets:llms_txt"))
        assert b"No brand assets are currently published." in response.content
