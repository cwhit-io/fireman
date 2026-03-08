import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestCutterProgramModel:
    def test_create_program(self):
        from apps.cutter.models import CutterProgram

        p = CutterProgram.objects.create(name="BC Standard", duplo_code="BC001")
        assert str(p) == "BC Standard (BC001)"


class TestBarcodeGeneration:
    def test_generate_code39_barcode_returns_png(self):
        from apps.cutter.services import generate_code39_barcode

        png = generate_code39_barcode("123")
        assert png[:4] == b"\x89PNG"

    def test_barcode_pdf_snippet(self):
        from apps.cutter.services import barcode_pdf_snippet

        pdf = barcode_pdf_snippet("001", x=36, y=36, width=90, height=25)
        assert pdf[:4] == b"%PDF"


class TestProgramBarcodeView:
    def test_barcode_endpoint_returns_png(self, client):
        from apps.cutter.models import CutterProgram

        program = CutterProgram.objects.create(name="Test Prog", duplo_code="T001")
        response = client.get(reverse("cutter:barcode", kwargs={"pk": program.pk}))
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert response.content[:4] == b"\x89PNG"

    def test_barcode_endpoint_404_for_missing(self, client):
        response = client.get(reverse("cutter:barcode", kwargs={"pk": 9999}))
        assert response.status_code == 404
