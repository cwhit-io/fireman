import io

import pytest

pytestmark = pytest.mark.django_db


def _make_minimal_pdf() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 252 144]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
        b"0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )


class TestImposeNup:
    def test_2up_produces_output(self):
        from pypdf import PdfReader

        from apps.impose.services import impose_nup

        inp = io.BytesIO(_make_minimal_pdf())
        out = io.BytesIO()
        impose_nup(inp, out, columns=2, rows=1, sheet_width=504, sheet_height=288)
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 1

    def test_business_card_21up(self):
        from pypdf import PdfReader

        from apps.impose.services import impose_business_card_21up

        inp = io.BytesIO(_make_minimal_pdf())
        out = io.BytesIO()
        impose_business_card_21up(inp, out)
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) >= 1


class TestImpositionTemplateModel:
    def test_create_template(self):
        from apps.impose.models import ImpositionTemplate
        t = ImpositionTemplate.objects.create(
            name="Test 2-Up",
            layout_type=ImpositionTemplate.LayoutType.TWO_UP,
            sheet_width=1224,
            sheet_height=792,
            columns=2,
            rows=1,
        )
        assert str(t) == "Test 2-Up"
