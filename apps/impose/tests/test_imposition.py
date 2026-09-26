import io
import re

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


class TestComputeArtworkPlacement:
    """Numeric tests for trim-to-trim vs no-bleed cover placement."""

    def _cell(
        self, cut_w=288.0, cut_h=432.0, bleed=9.0, margin_left=0.0, margin_top=0.0
    ):
        cell_w = cut_w + 2 * bleed
        cell_h = cut_h + 2 * bleed
        return {
            "cell_w": cell_w,
            "cell_h": cell_h,
            "cell_trim_left": margin_left + bleed,
            "cell_trim_bottom": bleed,  # single row, origin at sheet bottom of cell
            "bleed": bleed,
            "cut_w": cut_w,
            "cut_h": cut_h,
        }

    def test_inferred_bleed_is_trim_to_trim(self):
        """4.25×6.25" source into 4×6" + 0.125" cell → scale 1, trim origins match."""
        from apps.impose.services import compute_artwork_placement

        cell = self._cell()
        p = compute_artwork_placement(
            src_trim_w=288.0,
            src_trim_h=432.0,
            src_trim_left=9.0,
            src_trim_bottom=9.0,
            src_media_w=306.0,
            src_media_h=450.0,
            src_media_left=0.0,
            src_media_bottom=0.0,
            cell_w=cell["cell_w"],
            cell_h=cell["cell_h"],
            cell_trim_left=cell["cell_trim_left"],
            cell_trim_bottom=cell["cell_trim_bottom"],
            bleed=cell["bleed"],
        )
        assert p.src_has_bleed is True
        assert p.scale == pytest.approx(1.0)
        # Source trim (9, 9) maps onto cell trim origin.
        mx, my = p.map_point(9.0, 9.0)
        assert mx == pytest.approx(cell["cell_trim_left"])
        assert my == pytest.approx(cell["cell_trim_bottom"])
        # Source MediaBox origin maps onto cell bleed origin.
        ox, oy = p.map_point(0.0, 0.0)
        assert ox == pytest.approx(cell["cell_trim_left"] - 9.0)
        assert oy == pytest.approx(cell["cell_trim_bottom"] - 9.0)
        # Clip keeps template bleed (9pt) around trim in source space.
        assert p.clip_x == pytest.approx(0.0)
        assert p.clip_y == pytest.approx(0.0)
        assert p.clip_w == pytest.approx(306.0)
        assert p.clip_h == pytest.approx(450.0)

    def test_explicit_trimbox_same_as_inferred(self):
        from apps.impose.services import compute_artwork_placement

        cell = self._cell()
        p = compute_artwork_placement(
            src_trim_w=288.0,
            src_trim_h=432.0,
            src_trim_left=9.0,
            src_trim_bottom=9.0,
            src_media_w=306.0,
            src_media_h=450.0,
            src_media_left=0.0,
            src_media_bottom=0.0,
            **{
                k: cell[k]
                for k in (
                    "cell_w",
                    "cell_h",
                    "cell_trim_left",
                    "cell_trim_bottom",
                    "bleed",
                )
            },
        )
        assert p.scale == pytest.approx(1.0)
        assert p.src_has_bleed is True

    def test_larger_source_bleed_clipped_to_template(self):
        """0.25" source bleed into 0.125" template: trim-to-trim, clip to 9pt."""
        from apps.impose.services import compute_artwork_placement

        cell = self._cell()
        p = compute_artwork_placement(
            src_trim_w=288.0,
            src_trim_h=432.0,
            src_trim_left=18.0,
            src_trim_bottom=18.0,
            src_media_w=324.0,
            src_media_h=468.0,
            src_media_left=0.0,
            src_media_bottom=0.0,
            cell_w=cell["cell_w"],
            cell_h=cell["cell_h"],
            cell_trim_left=cell["cell_trim_left"],
            cell_trim_bottom=cell["cell_trim_bottom"],
            bleed=cell["bleed"],
        )
        assert p.src_has_bleed is True
        assert p.scale == pytest.approx(1.0)
        mx, my = p.map_point(18.0, 18.0)
        assert mx == pytest.approx(cell["cell_trim_left"])
        assert my == pytest.approx(cell["cell_trim_bottom"])
        assert p.clip_x == pytest.approx(9.0)  # 18 - 9
        assert p.clip_y == pytest.approx(9.0)
        assert p.clip_w == pytest.approx(288.0 + 18.0)
        assert p.clip_h == pytest.approx(432.0 + 18.0)

    def test_no_bleed_covers_full_cell(self):
        """Exact 4×6" source is stretched to fill trim + bleed (R1)."""
        from apps.impose.services import compute_artwork_placement

        cell = self._cell()
        p = compute_artwork_placement(
            src_trim_w=288.0,
            src_trim_h=432.0,
            src_trim_left=0.0,
            src_trim_bottom=0.0,
            src_media_w=288.0,
            src_media_h=432.0,
            src_media_left=0.0,
            src_media_bottom=0.0,
            cell_w=cell["cell_w"],
            cell_h=cell["cell_h"],
            cell_trim_left=cell["cell_trim_left"],
            cell_trim_bottom=cell["cell_trim_bottom"],
            bleed=cell["bleed"],
        )
        assert p.src_has_bleed is False
        # Cover uses max(cell/trim). Adding equal bleed to both axes changes AR,
        # so the scaled page overflows the long axis and is centred.
        assert p.scale == pytest.approx(cell["cell_w"] / 288.0)  # 306/288
        cell_origin_x = cell["cell_trim_left"] - cell["bleed"]
        cell_origin_y = cell["cell_trim_bottom"] - cell["bleed"]
        placed_w = 288.0 * p.scale
        placed_h = 432.0 * p.scale
        assert placed_w >= cell["cell_w"] - 1e-6
        assert placed_h >= cell["cell_h"] - 1e-6
        ox, oy = p.map_point(0.0, 0.0)
        assert ox == pytest.approx(cell_origin_x + (cell["cell_w"] - placed_w) / 2)
        assert oy == pytest.approx(cell_origin_y + (cell["cell_h"] - placed_h) / 2)

    def test_center_mode_no_bleed_fits_inside_trim(self):
        """Center mode: exact 4×6" source stays at scale 1, centred in the trim."""
        from apps.impose.services import compute_artwork_placement

        cell = self._cell()
        p = compute_artwork_placement(
            src_trim_w=288.0,
            src_trim_h=432.0,
            src_trim_left=0.0,
            src_trim_bottom=0.0,
            src_media_w=288.0,
            src_media_h=432.0,
            src_media_left=0.0,
            src_media_bottom=0.0,
            cell_w=cell["cell_w"],
            cell_h=cell["cell_h"],
            cell_trim_left=cell["cell_trim_left"],
            cell_trim_bottom=cell["cell_trim_bottom"],
            bleed=cell["bleed"],
            fit_mode="center",
        )
        assert p.src_has_bleed is False
        # MediaBox == trim, so scale is min(trim/media) = 1.0 in both axes.
        assert p.scale == pytest.approx(1.0)
        # Page fills the trim area exactly, centred in the cell.
        ox, oy = p.map_point(0.0, 0.0)
        assert ox == pytest.approx(cell["cell_trim_left"])
        assert oy == pytest.approx(cell["cell_trim_bottom"])
        # Clip covers the whole MediaBox (nothing to trim away in center mode).
        assert p.clip_x == pytest.approx(0.0)
        assert p.clip_y == pytest.approx(0.0)
        assert p.clip_w == pytest.approx(288.0)
        assert p.clip_h == pytest.approx(432.0)

    def test_center_mode_fits_trim_when_cut_size_matches(self):
        """Center mode: a source smaller than the cell trim is centred unscaled."""
        from apps.impose.services import compute_artwork_placement

        # Cell trim is 288×432; source page is 216×216 (smaller both axes).
        p = compute_artwork_placement(
            src_trim_w=216.0,
            src_trim_h=216.0,
            src_trim_left=0.0,
            src_trim_bottom=0.0,
            src_media_w=216.0,
            src_media_h=216.0,
            src_media_left=0.0,
            src_media_bottom=0.0,
            cell_w=306.0,
            cell_h=450.0,
            cell_trim_left=9.0,
            cell_trim_bottom=9.0,
            bleed=9.0,
            fit_mode="center",
        )
        # Never enlarged beyond its own size, even though the trim is bigger.
        assert p.scale == pytest.approx(1.0)
        # Centred: leftover space split evenly on each axis.
        ox, oy = p.map_point(0.0, 0.0)
        assert ox == pytest.approx(9.0 + (288.0 - 216.0) / 2)
        assert oy == pytest.approx(9.0 + (432.0 - 216.0) / 2)

    def test_center_mode_oversized_page_scaled_down(self):
        """Center mode: a page larger than the cell trim is uniformly shrunk."""
        from apps.impose.services import compute_artwork_placement

        # Source 400×600 into a 288×432 trim → scale limited by height.
        p = compute_artwork_placement(
            src_trim_w=400.0,
            src_trim_h=600.0,
            src_trim_left=0.0,
            src_trim_bottom=0.0,
            src_media_w=400.0,
            src_media_h=600.0,
            src_media_left=0.0,
            src_media_bottom=0.0,
            cell_w=306.0,
            cell_h=450.0,
            cell_trim_left=9.0,
            cell_trim_bottom=9.0,
            bleed=9.0,
            fit_mode="center",
        )
        expected_scale = 432.0 / 600.0
        assert p.scale == pytest.approx(expected_scale)
        # The scaled page must fit inside the trim on both axes.
        placed_w = 400.0 * p.scale
        placed_h = 600.0 * p.scale
        assert placed_w <= 288.0 + 1e-6
        assert placed_h <= 432.0 + 1e-6
        # Centred horizontally: leftover width split evenly.
        ox, _ = p.map_point(0.0, 0.0)
        assert ox == pytest.approx(9.0 + (288.0 - placed_w) / 2)

    def test_center_mode_with_source_bleed_keeps_trim_size(self):
        """Center mode: 4.25×6.25" source is clipped to its trim and fitted, not
        stretched — the artwork is never scaled up to fill the bleed gutter."""
        from apps.impose.services import compute_artwork_placement

        cell = self._cell()
        p = compute_artwork_placement(
            src_trim_w=288.0,
            src_trim_h=432.0,
            src_trim_left=9.0,
            src_trim_bottom=9.0,
            src_media_w=306.0,
            src_media_h=450.0,
            src_media_left=0.0,
            src_media_bottom=0.0,
            cell_w=cell["cell_w"],
            cell_h=cell["cell_h"],
            cell_trim_left=cell["cell_trim_left"],
            cell_trim_bottom=cell["cell_trim_bottom"],
            bleed=cell["bleed"],
            fit_mode="center",
        )
        assert p.src_has_bleed is True
        # Center mode fits the whole MediaBox (306×450) inside the cell trim
        # (288×432) — the limiting axis is width → 288/306, capped at 1.0.
        assert p.scale == pytest.approx(288.0 / 306.0)
        # The whole MediaBox (including its bleed margin) must sit inside the
        # cell's trim area.
        placed_w = 306.0 * p.scale
        placed_h = 450.0 * p.scale
        assert placed_w <= 288.0 + 1e-6
        assert placed_h <= 432.0 + 1e-6
        # Centred within the cell trim: leftover space split evenly.
        ox, oy = p.map_point(0.0, 0.0)
        assert ox == pytest.approx(cell["cell_trim_left"] + (288.0 - placed_w) / 2)
        assert oy == pytest.approx(cell["cell_trim_bottom"] + (432.0 - placed_h) / 2)
        # Clip covers the whole MediaBox, including the source bleed margin.
        assert p.clip_x == pytest.approx(0.0)
        assert p.clip_y == pytest.approx(0.0)
        assert p.clip_w == pytest.approx(306.0)
        assert p.clip_h == pytest.approx(450.0)

    def test_default_fit_mode_is_cover(self):
        """Omitting fit_mode reproduces the legacy cover behaviour exactly."""
        from apps.impose.services import compute_artwork_placement

        cell = self._cell()
        kwargs = {
            "src_trim_w": 288.0,
            "src_trim_h": 432.0,
            "src_trim_left": 0.0,
            "src_trim_bottom": 0.0,
            "src_media_w": 288.0,
            "src_media_h": 432.0,
            "src_media_left": 0.0,
            "src_media_bottom": 0.0,
            "cell_w": cell["cell_w"],
            "cell_h": cell["cell_h"],
            "cell_trim_left": cell["cell_trim_left"],
            "cell_trim_bottom": cell["cell_trim_bottom"],
            "bleed": cell["bleed"],
        }
        default = compute_artwork_placement(**kwargs)
        explicit = compute_artwork_placement(**kwargs, fit_mode="cover")
        assert default == explicit


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

    def test_center_mode_placed_at_trim_origin(self):
        """1-up center mode: page content lands at the trim origin, unscaled.

        A 288×432 page imposed 1-up on a 306×450 sheet with 9pt bleed: center
        mode keeps scale 1.0 and translates the content to (9, 9); cover mode
        would scale to 1.0625.
        """
        from pypdf import PdfReader
        from pypdf.generic import DecodedStreamObject, NameObject

        from apps.impose.services import impose_nup

        def _make_page_pdf() -> bytes:
            buf = io.BytesIO()
            writer = PdfWriter()
            page = PageObject.create_blank_page(width=288, height=432)
            stream = DecodedStreamObject()
            stream.set_data(b"0 0 288 432 re f\n")
            page[NameObject("/Contents")] = stream
            writer.add_page(page)
            writer.write(buf)
            return buf.getvalue()

        inp = io.BytesIO(_make_page_pdf())
        out = io.BytesIO()
        impose_nup(
            inp,
            out,
            columns=1,
            rows=1,
            sheet_width=306,
            sheet_height=450,
            bleed=9.0,
            fit_mode="center",
        )
        out.seek(0)
        data = PdfReader(out).pages[0].get_contents().get_data()
        # Collect every cm matrix in the merged content stream.
        matrices = []
        for m in re.finditer(
            rb"(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+"
            rb"(-?[\d.]+)\s+(-?[\d.]+)\s+cm",
            data,
        ):
            a, b, c, d, e, f = (float(g) for g in m.groups())
            matrices.append((a, b, c, d, e, f))
        placement = [m for m in matrices if abs(m[0] - 1.0) < 0.01]
        assert placement, f"no unit-scale placement found in {matrices!r}"
        _, _, _, _, e, f = placement[0]
        assert e == pytest.approx(9.0, abs=0.5)
        assert f == pytest.approx(9.0, abs=0.5)

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
            sheet_width=1224,
            sheet_height=792,
            columns=2,
            rows=1,
        )
        assert str(t) == "Test 2-Up"


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
        from pypdf import PageObject, PdfReader, PdfWriter

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
            sheet_width=900,  # 12.5"
            sheet_height=1368,  # 19"
            cut_width=252,  # 3.5"
            cut_height=144,  # 2"
            bleed=9,  # 0.125"
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

    def test_cut_marks_use_cut_dimensions_when_grid_overflows(self):
        """Cut mark cells must match cut_width/cut_height even when the grid overflows the sheet.

        Previously, get_template_effective_margins() fell back to dividing the
        sheet evenly by columns/rows when the grid overflowed, which could flip
        the cell orientation and produce cut marks at wrong dimensions.
        """
        from apps.impose.models import ImpositionTemplate
        from apps.impose.services import get_template_effective_margins

        PT = 72.0  # points per inch

        # 4×5.5" cards, 2 cols × 4 rows on a 13×19" sheet.
        # Grid height = 4 × 5.5" = 22" > 19" — overflows.
        # Fallback used to produce 4.75"-tall cells (landscape); correct is 5.5" (portrait).
        tmpl = ImpositionTemplate(
            name="Overflow cut marks test",
            sheet_width=13 * PT,
            sheet_height=19 * PT,
            cut_width=4.25 * PT,
            cut_height=5.5 * PT,
            bleed=0.125 * PT,
            columns=2,
            rows=4,
        )

        layout = get_template_effective_margins(tmpl)

        expected_cell_w = round((4.25 + 2 * 0.125) * PT, 6)
        expected_cell_h = round((5.5 + 2 * 0.125) * PT, 6)

        assert abs(layout["cell_w"] - expected_cell_w) < 0.01, (
            f'cell_w should be {expected_cell_w:.2f} pt ({4.5}" incl bleed) '
            f"but got {layout['cell_w']:.2f}"
        )
        assert abs(layout["cell_h"] - expected_cell_h) < 0.01, (
            f'cell_h should be {expected_cell_h:.2f} pt ({5.75}" incl bleed) '
            f"but got {layout['cell_h']:.2f}"
        )
