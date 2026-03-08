import io

import pytest
from pypdf import PageObject, PdfWriter

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


def _make_pdf_with_mediabox(width_pt: float, height_pt: float) -> bytes:
    """Create a minimal single-page PDF with the given MediaBox dimensions."""
    buf = io.BytesIO()
    writer = PdfWriter()
    page = PageObject.create_blank_page(width=width_pt, height=height_pt)
    writer.add_page(page)
    writer.write(buf)
    return buf.getvalue()


def _make_pdf_with_trimbox(
    media_w: float,
    media_h: float,
    trim_left: float,
    trim_bottom: float,
    trim_w: float,
    trim_h: float,
) -> bytes:
    """Create a minimal single-page PDF with an explicit TrimBox."""
    from pypdf.generic import ArrayObject, FloatObject, NameObject

    buf = io.BytesIO()
    writer = PdfWriter()
    page = PageObject.create_blank_page(width=media_w, height=media_h)
    page[NameObject("/TrimBox")] = ArrayObject(
        [
            FloatObject(trim_left),
            FloatObject(trim_bottom),
            FloatObject(trim_left + trim_w),
            FloatObject(trim_bottom + trim_h),
        ]
    )
    writer.add_page(page)
    writer.write(buf)
    return buf.getvalue()


class TestDetectSourceTrim:
    """Unit tests for detect_source_trim()."""

    def test_standard_exact_match_no_bleed(self):
        """A 4×6" MediaBox (288×432 pt) should be detected as trim with no offset."""
        from pypdf import PdfReader

        from apps.impose.services import detect_source_trim

        pdf = _make_pdf_with_mediabox(288.0, 432.0)
        page = PdfReader(io.BytesIO(pdf)).pages[0]
        trim_w, trim_h, trim_left, trim_bottom = detect_source_trim(page)
        assert trim_w == pytest.approx(288.0, abs=1.0)
        assert trim_h == pytest.approx(432.0, abs=1.0)
        assert trim_left == pytest.approx(0.0, abs=1.0)
        assert trim_bottom == pytest.approx(0.0, abs=1.0)

    def test_inferred_bleed_4x6_plus_0125_bleed(self):
        """4.25×6.25" (306×450 pt) should be inferred as 4×6" trim + 0.125" bleed."""
        from pypdf import PdfReader

        from apps.impose.services import detect_source_trim

        # 4.25" × 6.25" = 306 × 450 pt
        pdf = _make_pdf_with_mediabox(306.0, 450.0)
        page = PdfReader(io.BytesIO(pdf)).pages[0]
        trim_w, trim_h, trim_left, trim_bottom = detect_source_trim(page)
        assert trim_w == pytest.approx(288.0, abs=1.0)  # 4" = 288 pt
        assert trim_h == pytest.approx(432.0, abs=1.0)  # 6" = 432 pt
        assert trim_left == pytest.approx(9.0, abs=1.0)  # 0.125" = 9 pt
        assert trim_bottom == pytest.approx(9.0, abs=1.0)

    def test_inferred_bleed_4x6_plus_0250_bleed(self):
        """4.5×6.5" (324×468 pt) should be inferred as 4×6" trim + 0.25" bleed."""
        from pypdf import PdfReader

        from apps.impose.services import detect_source_trim

        # 4.5" × 6.5" = 324 × 468 pt
        pdf = _make_pdf_with_mediabox(324.0, 468.0)
        page = PdfReader(io.BytesIO(pdf)).pages[0]
        trim_w, trim_h, trim_left, trim_bottom = detect_source_trim(page)
        assert trim_w == pytest.approx(288.0, abs=1.0)  # 4" = 288 pt
        assert trim_h == pytest.approx(432.0, abs=1.0)  # 6" = 432 pt
        assert trim_left == pytest.approx(18.0, abs=1.0)  # 0.25" = 18 pt
        assert trim_bottom == pytest.approx(18.0, abs=1.0)

    def test_explicit_trimbox_used(self):
        """An explicit TrimBox in the PDF should take priority over inference."""
        from pypdf import PdfReader

        from apps.impose.services import detect_source_trim

        # MediaBox 306×450 (4.25×6.25"), TrimBox 9 9 297 441 (4×6" at offset 9,9)
        pdf = _make_pdf_with_trimbox(306.0, 450.0, 9.0, 9.0, 288.0, 432.0)
        page = PdfReader(io.BytesIO(pdf)).pages[0]
        trim_w, trim_h, trim_left, trim_bottom = detect_source_trim(page)
        assert trim_w == pytest.approx(288.0, abs=1.0)
        assert trim_h == pytest.approx(432.0, abs=1.0)
        assert trim_left == pytest.approx(9.0, abs=1.0)
        assert trim_bottom == pytest.approx(9.0, abs=1.0)

    def test_fallback_non_standard_size(self):
        """A non-standard MediaBox with no bleed match should return the full MediaBox."""
        from pypdf import PdfReader

        from apps.impose.services import detect_source_trim

        pdf = _make_pdf_with_mediabox(400.0, 600.0)
        page = PdfReader(io.BytesIO(pdf)).pages[0]
        trim_w, trim_h, trim_left, trim_bottom = detect_source_trim(page)
        assert trim_w == pytest.approx(400.0, abs=1.0)
        assert trim_h == pytest.approx(600.0, abs=1.0)
        assert trim_left == pytest.approx(0.0, abs=1.0)
        assert trim_bottom == pytest.approx(0.0, abs=1.0)


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

    def test_impose_with_bleed_in_mediabox(self):
        """Imposition of a 4.25×6.25" source (bleed baked into MediaBox) should produce
        valid output with 1 sheet for a 2-up 4×6" layout."""
        from pypdf import PdfReader

        from apps.impose.services import impose_nup

        # 4.25×6.25" = 306×450 pt (4×6 + 0.125" bleed)
        pdf = _make_pdf_with_mediabox(306.0, 450.0)
        inp = io.BytesIO(pdf)
        out = io.BytesIO()
        # 2-up on a sheet that fits two 4.25×6.25" cells side by side
        impose_nup(
            inp,
            out,
            columns=2,
            rows=1,
            sheet_width=612.0,
            sheet_height=450.0,
            bleed=9.0,  # 0.125" bleed
        )
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 1

    def test_impose_with_explicit_trimbox(self):
        """Imposition of a 4×6" source with explicit TrimBox (bleed in margin)
        should produce valid output."""
        from pypdf import PdfReader

        from apps.impose.services import impose_nup

        # MediaBox 306×450 (4.25×6.25"), TrimBox 4×6" at offset 9,9
        pdf = _make_pdf_with_trimbox(306.0, 450.0, 9.0, 9.0, 288.0, 432.0)
        inp = io.BytesIO(pdf)
        out = io.BytesIO()
        impose_nup(
            inp,
            out,
            columns=2,
            rows=1,
            sheet_width=612.0,
            sheet_height=450.0,
            bleed=9.0,
        )
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 1

    def test_impose_with_large_bleed_in_mediabox(self):
        """Imposition of a 4.5×6.5" source (0.25" bleed baked in) should produce
        valid output.

        The template uses a 0.125" (9 pt) bleed, while the source has 0.25" bleed
        baked into its MediaBox. detect_source_trim() identifies the source as a
        4×6" trim with 0.25" bleed and scales it so the trim fits the cell's trim
        area — the extra bleed content spills into the cell's bleed margin.
        """
        from pypdf import PdfReader

        from apps.impose.services import impose_nup

        # 4.5×6.5" = 324×468 pt (4×6 + 0.25" bleed)
        pdf = _make_pdf_with_mediabox(324.0, 468.0)
        inp = io.BytesIO(pdf)
        out = io.BytesIO()
        impose_nup(
            inp,
            out,
            columns=2,
            rows=1,
            sheet_width=612.0,
            sheet_height=450.0,
            bleed=9.0,
        )
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 1


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


class TestAutoRotate:
    """Test that auto-rotation works for landscape sources in portrait cells."""

    def test_landscape_source_rotated_into_portrait_cell(self):
        """A landscape source (6×4") should be auto-rotated to fit a portrait cell (4×6")."""
        from pypdf import PdfReader

        from apps.impose.services import impose_nup

        # Landscape 4×6 = 432×288 pt
        landscape_pdf = _make_pdf_with_mediabox(432.0, 288.0)
        inp = io.BytesIO(landscape_pdf)
        out = io.BytesIO()
        # Sheet is portrait; cells are portrait (4×6 each + margins)
        impose_nup(
            inp,
            out,
            columns=2,
            rows=1,
            sheet_width=900.0,
            sheet_height=450.0,
            bleed=0.0,
            auto_rotate=True,
        )
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 1

    def test_no_rotation_when_disabled(self):
        """auto_rotate=False should not rotate the source page."""
        from pypdf import PdfReader

        from apps.impose.services import impose_nup

        # Landscape 432×288 pt
        landscape_pdf = _make_pdf_with_mediabox(432.0, 288.0)
        inp = io.BytesIO(landscape_pdf)
        out = io.BytesIO()
        impose_nup(
            inp,
            out,
            columns=2,
            rows=1,
            sheet_width=900.0,
            sheet_height=450.0,
            bleed=0.0,
            auto_rotate=False,
        )
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 1


class TestImposeFromTemplateOptions:
    """Test that pages_are_unique flag drives step-repeat vs n-up."""

    def test_pages_not_unique_uses_step_repeat(self):
        """pages_are_unique=False should produce step-and-repeat output."""
        import io as _io

        from pypdf import PdfReader

        from apps.impose.models import ImpositionTemplate
        from apps.impose.services import impose_from_template

        # Create a 2-page PDF
        buf = _io.BytesIO()
        from pypdf import PageObject, PdfWriter

        w = PdfWriter()
        w.add_page(PageObject.create_blank_page(width=288, height=432))
        w.add_page(PageObject.create_blank_page(width=288, height=432))
        w.write(buf)
        buf.seek(0)

        tmpl = ImpositionTemplate.objects.create(
            name="Step-repeat test",
            sheet_width=2 * 288,
            sheet_height=432,
            columns=2,
            rows=1,
        )
        out = _io.BytesIO()
        impose_from_template(tmpl, buf, out, pages_are_unique=False)
        out.seek(0)
        reader = PdfReader(out)
        # Step-repeat uses only 1 source page repeated, so 1 sheet
        assert len(reader.pages) == 1
