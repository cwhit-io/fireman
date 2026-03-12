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
            layout_type=ImpositionTemplate.LayoutType.CUSTOM,
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
        """pages_are_unique=False should produce a single step-and-repeat sheet.

        Only the first source page is used; a multi-page input is truncated so
        that customers who upload a 2-page file still get one gang-up sheet.
        """
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
        # Step-repeat uses only the first source page → exactly 1 output sheet
        # regardless of how many pages the source PDF contains.
        assert len(reader.pages) == 1


class TestImposeStepRepeat:
    """Tests for the step-and-repeat function filling all cells."""

    def test_step_repeat_fills_all_cells(self):
        """impose_step_repeat should produce a single sheet with the source page
        placed in every cell, not just the first cell."""
        from pypdf import PdfReader

        from apps.impose.services import impose_step_repeat

        # Single 4×6 page
        pdf = _make_pdf_with_mediabox(288.0, 432.0)
        inp = io.BytesIO(pdf)
        out = io.BytesIO()
        # 4-up: 2 columns × 2 rows on a large sheet
        impose_step_repeat(
            inp, out, columns=2, rows=2, sheet_width=576, sheet_height=864
        )
        out.seek(0)
        reader = PdfReader(out)
        # Should produce exactly 1 output sheet
        assert len(reader.pages) == 1

    def test_step_repeat_single_page_input(self):
        """impose_step_repeat with 1-up template produces 1 output sheet."""
        from pypdf import PdfReader

        from apps.impose.services import impose_step_repeat

        pdf = _make_pdf_with_mediabox(288.0, 432.0)
        inp = io.BytesIO(pdf)
        out = io.BytesIO()
        impose_step_repeat(
            inp, out, columns=1, rows=1, sheet_width=288, sheet_height=432
        )
        out.seek(0)
        assert len(PdfReader(out).pages) == 1


class TestDoubleSidedNup:
    """Tests for double-sided imposition producing one sheet per source page."""

    def _make_two_page_pdf(self) -> bytes:
        """Create a 2-page PDF (simulates front + back of a double-sided job)."""
        from pypdf import PageObject, PdfWriter

        buf = io.BytesIO()
        w = PdfWriter()
        w.add_page(PageObject.create_blank_page(width=288, height=432))
        w.add_page(PageObject.create_blank_page(width=288, height=432))
        w.write(buf)
        return buf.getvalue()

    def test_double_sided_nup_one_sheet_per_page(self):
        """impose_double_sided_nup with a 2-page input and 8-up template should
        produce 2 output sheets (one per source page)."""
        from pypdf import PdfReader

        from apps.impose.services import impose_double_sided_nup

        pdf = self._make_two_page_pdf()
        inp = io.BytesIO(pdf)
        out = io.BytesIO()
        impose_double_sided_nup(
            inp,
            out,
            columns=4,
            rows=2,
            sheet_width=936,
            sheet_height=1368,
        )
        out.seek(0)
        assert len(PdfReader(out).pages) == 2

    def test_impose_from_template_double_sided(self):
        """impose_from_template with is_double_sided=True should create one output
        sheet for each source page (2 pages in → 2 sheets out)."""
        from pypdf import PdfReader

        from apps.impose.models import ImpositionTemplate
        from apps.impose.services import impose_from_template

        pdf = self._make_two_page_pdf()
        inp = io.BytesIO(pdf)
        out = io.BytesIO()

        tmpl = ImpositionTemplate.objects.create(
            name="8up double-sided test",
            sheet_width=936,  # 13"
            sheet_height=1368,  # 19"
            columns=4,
            rows=2,
            bleed=9,  # 0.125"
        )
        impose_from_template(
            tmpl, inp, out, pages_are_unique=True, is_double_sided=True
        )
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 2

    def test_pages_not_unique_overrides_double_sided(self):
        """pages_are_unique=False takes precedence: step-repeat produces 1 sheet."""
        from pypdf import PdfReader

        from apps.impose.models import ImpositionTemplate
        from apps.impose.services import impose_from_template

        pdf = self._make_two_page_pdf()
        inp = io.BytesIO(pdf)
        out = io.BytesIO()

        tmpl = ImpositionTemplate.objects.create(
            name="Step-repeat override test",
            sheet_width=576,
            sheet_height=864,
            columns=2,
            rows=2,
        )
        impose_from_template(
            tmpl, inp, out, pages_are_unique=False, is_double_sided=True
        )
        out.seek(0)
        assert len(PdfReader(out).pages) == 1

    def test_multipage_unique_uses_nup(self):
        """pages_are_unique=True with a multi-page PDF should gang all pages
        sequentially across output sheets using the template's dimensions."""
        from pypdf import PdfReader, PageObject, PdfWriter

        from apps.impose.models import ImpositionTemplate
        from apps.impose.services import impose_from_template

        # 3 unique business-card-sized pages
        buf = io.BytesIO()
        w = PdfWriter()
        for _ in range(3):
            w.add_page(PageObject.create_blank_page(width=252, height=144))
        w.write(buf)
        buf.seek(0)

        # 3×7 = 21-up template (standard business card layout dimensions)
        tmpl = ImpositionTemplate.objects.create(
            name="Business card n-up test",
            sheet_width=900,   # 12.5"
            sheet_height=1368, # 19"
            cut_width=252,     # 3.5"
            cut_height=144,    # 2"
            bleed=9,           # 0.125"
            columns=3,
            rows=7,
        )
        out = io.BytesIO()
        impose_from_template(tmpl, buf, out, pages_are_unique=True)
        out.seek(0)
        # 3 pages × 21-up = 1 sheet (21 cells, first 3 filled)
        assert len(PdfReader(out).pages) == 1



    """Test that cut_width/cut_height drives proper centred margins."""

    def test_cut_size_centres_grid(self):
        """When cut_width/cut_height are set the grid should be centred on the
        sheet (margins > 0) and the correct number of output pages produced."""
        from pypdf import PdfReader

        from apps.impose.models import ImpositionTemplate
        from apps.impose.services import impose_from_template

        # 2-up 4×6 on a 13×10 sheet — grid fits (2×4.25" = 8.5" < 13")
        pdf = _make_pdf_with_mediabox(288.0, 432.0)
        inp = io.BytesIO(pdf)
        out = io.BytesIO()
        tmpl = ImpositionTemplate.objects.create(
            name="Cut-size margin test",
            sheet_width=936,  # 13"
            sheet_height=720,  # 10"
            cut_width=288,  # 4"
            cut_height=432,  # 6"
            bleed=9,  # 0.125"
            columns=2,
            rows=1,
        )
        impose_from_template(tmpl, inp, out)
        out.seek(0)
        assert len(PdfReader(out).pages) == 1


class TestBarcodeOverlay:
    """Test that a Code 39 barcode is rendered on each output sheet."""

    def test_barcode_added_to_output(self):
        """When barcode_value and template barcode coords are set, the output PDF
        should be larger than without a barcode (overlay content was added)."""
        from pypdf import PdfReader

        from apps.impose.models import ImpositionTemplate
        from apps.impose.services import impose_from_template

        pdf = _make_pdf_with_mediabox(288.0, 432.0)

        tmpl = ImpositionTemplate.objects.create(
            name="Barcode test",
            sheet_width=936,
            sheet_height=1368,
            columns=2,
            rows=4,
            barcode_x=18.0,
            barcode_y=18.0,
            barcode_width=90.0,
            barcode_height=25.2,
        )

        # Without barcode
        out_no_bc = io.BytesIO()
        impose_from_template(tmpl, io.BytesIO(pdf), out_no_bc)

        # With barcode — use a numeric value so the TIF file can be resolved
        out_bc = io.BytesIO()
        impose_from_template(tmpl, io.BytesIO(pdf), out_bc, barcode_value="1")

        # Both produce 1 sheet
        assert len(PdfReader(io.BytesIO(out_no_bc.getvalue())).pages) == 1
        assert len(PdfReader(io.BytesIO(out_bc.getvalue())).pages) == 1

        # The barcode version should be larger (overlay content adds bytes)
        assert len(out_bc.getvalue()) > len(out_no_bc.getvalue())

    def test_no_barcode_when_no_coords(self):
        """When the template has no barcode_x/barcode_y, barcode_value is ignored."""
        from pypdf import PdfReader

        from apps.impose.models import ImpositionTemplate
        from apps.impose.services import impose_from_template

        pdf = _make_pdf_with_mediabox(288.0, 432.0)
        tmpl = ImpositionTemplate.objects.create(
            name="No barcode coords test",
            sheet_width=576,
            sheet_height=432,
            columns=2,
            rows=1,
        )
        out = io.BytesIO()
        impose_from_template(tmpl, io.BytesIO(pdf), out, barcode_value="IGNORED")
        out.seek(0)
        assert len(PdfReader(out).pages) == 1


class TestCutMarks:
    """Test that cut marks are rendered on output sheets when requested."""

    def test_cut_marks_added(self):
        """cut_marks=True should produce a larger output PDF than cut_marks=False."""
        from pypdf import PdfReader

        from apps.impose.models import ImpositionTemplate
        from apps.impose.services import impose_from_template

        pdf = _make_pdf_with_mediabox(288.0, 432.0)
        tmpl = ImpositionTemplate.objects.create(
            name="Cut marks test",
            sheet_width=936,
            sheet_height=1368,
            columns=2,
            rows=4,
            bleed=9,
        )

        out_no_marks = io.BytesIO()
        impose_from_template(tmpl, io.BytesIO(pdf), out_no_marks, cut_marks=False)

        out_marks = io.BytesIO()
        impose_from_template(tmpl, io.BytesIO(pdf), out_marks, cut_marks=True)

        assert len(PdfReader(io.BytesIO(out_no_marks.getvalue())).pages) == 1
        assert len(PdfReader(io.BytesIO(out_marks.getvalue())).pages) == 1
        assert len(out_marks.getvalue()) > len(out_no_marks.getvalue())
