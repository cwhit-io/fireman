import pytest

pytestmark = pytest.mark.django_db


class TestCutterProgramModel:
    def test_create_program(self):
        from apps.cutter.models import CutterProgram
        p = CutterProgram.objects.create(name="BC Standard", duplo_code="BC001")
        assert str(p) == "BC Standard (BC001)"


class TestBarcodeGeneration:
    def test_generate_qr_barcode_returns_png(self):
        from apps.cutter.services import generate_qr_barcode
        png = generate_qr_barcode("TEST001")
        assert png[:4] == b"\x89PNG"

    def test_barcode_pdf_snippet(self):
        from apps.cutter.services import barcode_pdf_snippet
        pdf = barcode_pdf_snippet("PROG001", x=36, y=36, size=72)
        assert pdf[:4] == b"%PDF"
