import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestCutterProgramModel:
    def test_create_program(self):
        from apps.cutter.models import CutterProgram

        p = CutterProgram.objects.create(name="BC Standard", duplo_code="BC001")
        assert str(p) == "BC Standard (BC001)"


class TestProgramBarcodeView:
    def test_barcode_endpoint_404_for_missing(self, client):
        response = client.get(reverse("cutter:barcode", kwargs={"pk": 9999}))
        assert response.status_code == 404
