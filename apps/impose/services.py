"""
Imposition services — wrap PyPDF to place input pages onto press sheets.
"""

from __future__ import annotations

import io
import logging
import xml.etree.ElementTree as ET
from typing import IO

logger = logging.getLogger(__name__)

# ── PDF geometry helpers ───────────────────────────────────────────────────

# Well-known print trim sizes in PDF points (1 pt = 1/72 in).
# These are the *finished* (cut) dimensions without bleed.
_STANDARD_TRIM_SIZES_PT: dict[str, tuple[float, float]] = {
    'Business Card (3.5×2")': (252.0, 144.0),
    '4×6"': (288.0, 432.0),
    '5×7"': (360.0, 504.0),
    '5×8"': (360.0, 576.0),
    'Half Letter (5.5×8.5")': (396.0, 612.0),
    '6×9"': (432.0, 648.0),
    '8×10"': (576.0, 720.0),
    'Letter (8.5×11")': (612.0, 792.0),
    'Tabloid (11×17")': (792.0, 1224.0),
    '12×18"': (864.0, 1296.0),
}

# Common bleed amounts in PDF points to probe when inferring trim from MediaBox.
_COMMON_BLEEDS_PT: tuple[float, ...] = (
    9.0,  # 0.125" (1/8") — industry standard
    4.5,  # 0.0625" (1/16")
    3 * 72 / 25.4,  # 3 mm ≈ 8.504 pt
    5 * 72 / 25.4,  # 5 mm ≈ 14.173 pt
    18.0,  # 0.25" (1/4")
)

# Tolerance for dimension matching (pts).
_DIM_TOL_PT: float = 3.0

# mm → PDF points conversion factor.
_MM_TO_PT: float = 72.0 / 25.4

# SVG namespace used by python-barcode.
_SVG_NS: str = "http://www.w3.org/2000/svg"


def detect_source_trim(page) -> tuple[float, float, float, float]:
    """Detect the trim size and its position within a page's MediaBox.

    Returns ``(trim_w, trim_h, trim_left, trim_bottom)`` — all in PDF points.
    *trim_left* and *trim_bottom* are the absolute PDF coordinates of the
    trim box's bottom-left corner (the same coordinate space as MediaBox).

    Detection order:

    1. **Explicit TrimBox** — most reliable; used when the PDF contains a
       ``/TrimBox`` entry that differs from the MediaBox.
    2. **Standard exact match** — MediaBox dimensions equal a known trim size
       within ±3 pt; the page has no bleed content.
    3. **Inferred trim + bleed** — MediaBox = standard trim + a uniform bleed
       on all four sides (probes common bleed amounts: 0.0625", 0.125", …,
       0.25").  For example a 4.25 × 6.25" MediaBox is inferred as a 4 × 6"
       trim with a 0.125" bleed.
    4. **Fallback** — treat the full MediaBox as the trim (no bleed).
    """
    media = page.mediabox
    media_w = float(media.width)
    media_h = float(media.height)
    media_left = float(media.left)
    media_bottom = float(media.bottom)

    # 1. Explicit TrimBox ──────────────────────────────────────────────────
    if "/TrimBox" in page:
        tb = page.trimbox
        tb_w = float(tb.width)
        tb_h = float(tb.height)
        # Only use when it genuinely differs from the MediaBox.
        if abs(tb_w - media_w) > 1.0 or abs(tb_h - media_h) > 1.0:
            return (tb_w, tb_h, float(tb.left), float(tb.bottom))

    # 2. MediaBox exactly matches a known standard trim (no bleed) ─────────
    for sw, sh in _STANDARD_TRIM_SIZES_PT.values():
        if (abs(media_w - sw) < _DIM_TOL_PT and abs(media_h - sh) < _DIM_TOL_PT) or (
            abs(media_w - sh) < _DIM_TOL_PT and abs(media_h - sw) < _DIM_TOL_PT
        ):
            return (media_w, media_h, media_left, media_bottom)

    # 3. MediaBox = standard trim + uniform bleed (inferred) ───────────────
    best: tuple[float, float, float, float] | None = None
    best_err = float("inf")
    for sw, sh in _STANDARD_TRIM_SIZES_PT.values():
        for b in _COMMON_BLEEDS_PT:
            # Portrait orientation
            err = abs(media_w - (sw + 2 * b)) + abs(media_h - (sh + 2 * b))
            if err < best_err and err < _DIM_TOL_PT * 2:
                best_err = err
                best = (sw, sh, media_left + b, media_bottom + b)
            # Landscape orientation
            err = abs(media_w - (sh + 2 * b)) + abs(media_h - (sw + 2 * b))
            if err < best_err and err < _DIM_TOL_PT * 2:
                best_err = err
                best = (sh, sw, media_left + b, media_bottom + b)

    if best is not None:
        return best

    # 4. Fallback — full MediaBox is the trim ──────────────────────────────
    return (media_w, media_h, media_left, media_bottom)


def _pts(inches: float) -> float:
    return inches * 72.0


# ── Barcode rendering helpers ──────────────────────────────────────────────


def _barcode_pdf_stream(
    value: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> bytes:
    """Return PDF content-stream bytes that draw a Code 39 barcode.

    Uses python-barcode's SVG output to obtain the bar positions, then
    renders each bar as a filled PDF rectangle scaled to *width × height*
    points at position *(x, y)* (bottom-left corner in PDF coordinate space).

    Returns ``b""`` if *value* is empty or barcode generation fails.

    .. note::
        python-barcode's SVGWriter always outputs dimensions in millimetres.
        This function relies on that behaviour; if the unit ever changes the
        ``"mm"`` suffix check on line 160 will return early with an empty result.
    """
    if not value:
        return b""

    def _mm_attr(s: str) -> float:
        """Parse a CSS-millimetre attribute string such as ``'3.740mm'``."""
        stripped = s.replace("mm", "").strip()
        if not stripped:
            raise ValueError(s)
        return float(stripped)

    try:
        import barcode as _bc
        from barcode.writer import SVGWriter

        code = _bc.get("code39", value, writer=SVGWriter())
        buf = io.BytesIO()
        code.write(buf)
        buf.seek(0)
        svg_bytes = buf.read()
    except Exception:
        logger.exception("Barcode generation failed for value %r", value)
        return b""

    try:
        root = ET.fromstring(svg_bytes)
    except ET.ParseError:
        logger.warning("Barcode SVG parse error for value %r", value)
        return b""

    svg_w_str = root.get("width", "")
    if not svg_w_str.endswith("mm"):
        logger.warning(
            "Unexpected SVG width unit %r for barcode %r; expected 'mm'",
            svg_w_str,
            value,
        )
        return b""
    try:
        svg_w_pt = _mm_attr(svg_w_str) * _MM_TO_PT
    except ValueError:
        return b""

    if svg_w_pt <= 0:
        return b""

    x_scale = width / svg_w_pt

    cmds: list[bytes] = [b"q", b"0 0 0 rg"]
    for rect in root.iter(f"{{{_SVG_NS}}}rect"):
        style = rect.get("style", "")
        if "fill:black" not in style:
            continue
        try:
            rx_pt = _mm_attr(rect.get("x", "0mm")) * _MM_TO_PT
            rw_pt = _mm_attr(rect.get("width", "0mm")) * _MM_TO_PT
        except ValueError:
            continue
        bar_x = x + rx_pt * x_scale
        bar_w = rw_pt * x_scale
        if bar_w <= 0:
            continue
        cmds.append(f"{bar_x:.3f} {y:.3f} {bar_w:.3f} {height:.3f} re f".encode())

    if len(cmds) <= 2:
        return b""

    cmds.append(b"Q")
    return b"\n".join(cmds)


def _cut_marks_pdf_stream(
    cells: list[tuple[float, float, float, float]],
    bleed: float,
    offset: float = 5.0,
    length: float = 18.0,
    line_width: float = 0.5,
) -> bytes:
    """Return PDF content-stream bytes for press cut marks at each cell corner.

    *cells* is a list of ``(trim_left, trim_bottom, trim_w, trim_h)`` tuples,
    all in PDF points.  *offset* is the gap between the bleed edge and the
    start of the mark; *length* is how far the mark extends beyond the offset.
    """
    cmds: list[bytes] = [
        b"q",
        f"{line_width:.3f} w".encode(),
        b"0 0 0 RG",
    ]

    for trim_left, trim_bottom, trim_w, trim_h in cells:
        trim_right = trim_left + trim_w
        trim_top = trim_bottom + trim_h

        for cx, cy, dx, dy in (
            (trim_left, trim_bottom, -1, -1),
            (trim_right, trim_bottom, +1, -1),
            (trim_left, trim_top, -1, +1),
            (trim_right, trim_top, +1, +1),
        ):
            total = bleed + offset
            # horizontal arm
            hx1 = cx + dx * total
            hx2 = cx + dx * (total + length)
            cmds.append(
                f"{hx1:.3f} {cy:.3f} m {hx2:.3f} {cy:.3f} l S".encode()
            )
            # vertical arm
            vy1 = cy + dy * total
            vy2 = cy + dy * (total + length)
            cmds.append(
                f"{cx:.3f} {vy1:.3f} m {cx:.3f} {vy2:.3f} l S".encode()
            )

    cmds.append(b"Q")
    return b"\n".join(cmds)


def _make_overlay_page(sheet_w: float, sheet_h: float, content_stream: bytes):
    """Create a transparent PDF overlay page carrying *content_stream*.

    The page has the same dimensions as the press sheet so it can be merged
    directly onto an output sheet with ``page.merge_page()``.
    """
    from pypdf import PageObject, PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    stream = DecodedStreamObject()
    stream.set_data(content_stream)

    page = PageObject.create_blank_page(width=sheet_w, height=sheet_h)
    page[NameObject("/Contents")] = stream

    writer = PdfWriter()
    writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return PdfReader(buf).pages[0]


def impose_nup(
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
    columns: int,
    rows: int,
    sheet_width: float,
    sheet_height: float,
    bleed: float = 0.0,
    margin_top: float = 0.0,
    margin_right: float = 0.0,
    margin_bottom: float = 0.0,
    margin_left: float = 0.0,
    auto_rotate: bool = True,
) -> None:
    """
    Tile *columns × rows* source pages onto new press sheets and write to *output_pdf*.

    All dimensions are in PDF points (72 pts = 1 inch).

    The grid is automatically centered on the sheet when all four margins are
    zero (the default).  Explicit margins override centering.

    Each source page is analysed with :func:`detect_source_trim` so that the
    correct trim area is used for scaling — regardless of whether the uploaded
    file has bleed already baked into the MediaBox, stores it via an explicit
    TrimBox/BleedBox, or omits it entirely.

    When *auto_rotate* is ``True`` (the default), each source page is
    automatically rotated 90° to match the cell orientation — for example a
    landscape postcard source will be rotated to portrait when the imposition
    cells are portrait.  This removes the need to create separate templates for
    landscape and portrait versions of the same product.
    """
    from pypdf import PageObject, PdfReader, PdfWriter, Transformation

    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    per_sheet = columns * rows
    pages_up = list(reader.pages)
    if not pages_up:
        return

    # Cell size = bleed + trim + bleed
    cell_w = (sheet_width - margin_left - margin_right) / columns
    cell_h = (sheet_height - margin_top - margin_bottom) / rows

    # When all margins are zero, auto-centre the grid on the sheet.
    if margin_top == 0 and margin_right == 0 and margin_bottom == 0 and margin_left == 0:
        grid_w = columns * cell_w
        grid_h = rows * cell_h
        margin_left = (sheet_width - grid_w) / 2
        margin_top = (sheet_height - grid_h) / 2

    # Available area for the trim content inside each cell (excluding bleed border).
    cell_trim_w = cell_w - 2 * bleed
    cell_trim_h = cell_h - 2 * bleed

    for sheet_start in range(0, len(pages_up), per_sheet):
        sheet = PageObject.create_blank_page(width=sheet_width, height=sheet_height)
        for idx in range(per_sheet):
            page_idx = sheet_start + idx
            if page_idx >= len(pages_up):
                break
            src = pages_up[page_idx]

            col = idx % columns
            row = idx // columns

            # Detect the actual trim dimensions of the source page.
            src_trim_w, src_trim_h, src_trim_left, src_trim_bottom = detect_source_trim(
                src
            )

            # Auto-rotate: if source orientation doesn't match cell orientation, rotate 90°.
            rotated = False
            if auto_rotate:
                cell_is_portrait = cell_trim_h >= cell_trim_w
                src_is_portrait = src_trim_h >= src_trim_w
                if cell_is_portrait != src_is_portrait:
                    rotated = True

            # Bottom-left corner of the cell's trim area on the sheet.
            cell_trim_left = margin_left + col * cell_w + bleed
            cell_trim_bottom = sheet_height - margin_top - (row + 1) * cell_h + bleed

            if rotated:
                # 90° CW rotation: (x, y) → (y, −x)
                # After scaling by s: (x,y) → (s*y + tx, −s*x + ty)
                # Effective dimensions after rotation: width=trim_h, height=trim_w
                rot_trim_w = src_trim_h
                rot_trim_h = src_trim_w

                scale_x = cell_trim_w / rot_trim_w if rot_trim_w else 1.0
                scale_y = cell_trim_h / rot_trim_h if rot_trim_h else 1.0
                scale = min(scale_x, scale_y)

                center_x = (cell_trim_w - rot_trim_w * scale) / 2
                center_y = (cell_trim_h - rot_trim_h * scale) / 2

                target_left = cell_trim_left + center_x
                target_bottom = cell_trim_bottom + center_y

                # After 90° CW scale+rotate: bottom-left of rotated content on sheet:
                #   left  = s*src_trim_bottom + tx  → tx = target_left − s*src_trim_bottom
                #   bottom = −s*(src_trim_left+src_trim_w) + ty → ty = target_bottom + s*(src_trim_left+src_trim_w)
                tx = target_left - scale * src_trim_bottom
                ty = target_bottom + scale * (src_trim_left + src_trim_w)
                # Matrix: x′ = 0·x + s·y + tx,  y′ = −s·x + 0·y + ty
                transform = Transformation(ctm=(0, -scale, scale, 0, tx, ty))
            else:
                # Scale so the source trim fits the cell trim area (aspect-ratio preserved).
                scale_x = cell_trim_w / src_trim_w if src_trim_w else 1.0
                scale_y = cell_trim_h / src_trim_h if src_trim_h else 1.0
                scale = min(scale_x, scale_y)

                # Centre the scaled trim within the cell trim area.
                center_x = (cell_trim_w - src_trim_w * scale) / 2
                center_y = (cell_trim_h - src_trim_h * scale) / 2

                # Desired position for the source trim's bottom-left corner on the sheet.
                target_trim_left = cell_trim_left + center_x
                target_trim_bottom = cell_trim_bottom + center_y

                # Transformation: scale(s) then translate(tx, ty).
                tx = target_trim_left - scale * src_trim_left
                ty = target_trim_bottom - scale * src_trim_bottom

                transform = Transformation().scale(scale).translate(tx, ty)

            sheet.merge_transformed_page(src, transform)

        writer.add_page(sheet)

    writer.write(output_pdf)


def impose_step_repeat(
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
    columns: int,
    rows: int,
    sheet_width: float,
    sheet_height: float,
    bleed: float = 0.0,
) -> None:
    """Repeat a single source page *columns × rows* times (step-and-repeat).

    The first page of *input_pdf* is tiled to fill every cell on the sheet.
    All other pages in the input are ignored.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(input_pdf)
    if not reader.pages:
        return

    per_sheet = columns * rows
    buf = io.BytesIO()
    w = PdfWriter()
    # Repeat the first page once per cell so impose_nup fills every slot.
    for _ in range(per_sheet):
        w.add_page(reader.pages[0])
    w.write(buf)
    buf.seek(0)

    impose_nup(
        buf,
        output_pdf,
        columns=columns,
        rows=rows,
        sheet_width=sheet_width,
        sheet_height=sheet_height,
        bleed=bleed,
    )


def impose_double_sided_nup(
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
    columns: int,
    rows: int,
    sheet_width: float,
    sheet_height: float,
    bleed: float = 0.0,
    margin_top: float = 0.0,
    margin_right: float = 0.0,
    margin_bottom: float = 0.0,
    margin_left: float = 0.0,
    auto_rotate: bool = True,
) -> None:
    """Impose a double-sided job: each source page fills one output sheet.

    For a two-page front/back postcard with an 8-up template this produces:

    * Output sheet 1 — 8 copies of source page 1 (front)
    * Output sheet 2 — 8 copies of source page 2 (back)

    The output PDF can then be duplexed so that the front and back of every
    printed piece align correctly.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(input_pdf)
    if not reader.pages:
        return

    per_sheet = columns * rows
    final_writer = PdfWriter()

    for src_page in reader.pages:
        # Build a single-page PDF with per_sheet copies of this page.
        single_buf = io.BytesIO()
        w = PdfWriter()
        for _ in range(per_sheet):
            w.add_page(src_page)
        w.write(single_buf)
        single_buf.seek(0)

        sheet_buf = io.BytesIO()
        impose_nup(
            single_buf,
            sheet_buf,
            columns=columns,
            rows=rows,
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            bleed=bleed,
            margin_top=margin_top,
            margin_right=margin_right,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            auto_rotate=auto_rotate,
        )
        sheet_buf.seek(0)
        sheet_reader = PdfReader(sheet_buf)
        for sheet_page in sheet_reader.pages:
            final_writer.add_page(sheet_page)

    final_writer.write(output_pdf)


def impose_business_card_21up(
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
) -> None:
    """
    Standard 21-up business card imposition on a 12.5 × 19 in sheet.
    Business cards are 3.5 × 2 in; 3 columns × 7 rows.
    """
    impose_nup(
        input_pdf,
        output_pdf,
        columns=3,
        rows=7,
        sheet_width=_pts(12.5),
        sheet_height=_pts(19.0),
        bleed=_pts(0.125),
        margin_top=_pts(0.25),
        margin_right=_pts(0.25),
        margin_bottom=_pts(0.25),
        margin_left=_pts(0.25),
    )


def impose_from_template(
    template,
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
    pages_are_unique: bool = True,
    is_double_sided: bool = False,
    auto_rotate: bool = True,
    barcode_value: str | None = None,
    cut_marks: bool = False,
) -> None:
    """Dispatch imposition to the right function based on *template* settings.

    Modes
    -----
    * ``pages_are_unique=False`` or ``layout_type == STEP_REPEAT``:
      step-and-repeat — every cell on the sheet shows the same (first) page.
    * ``is_double_sided=True`` and ``pages_are_unique=True``:
      double-sided n-up — each source page fills one complete output sheet
      (e.g. page 1 × 8-up → sheet 1, page 2 × 8-up → sheet 2) so the job
      can be duplexed correctly.
    * Otherwise: standard sequential n-up.

    Post-processing overlays
    ------------------------
    When *barcode_value* is a non-empty string **and** the template has
    ``barcode_x``/``barcode_y`` coordinates, a Code 39 barcode is rendered on
    every output sheet at the position defined by the template.

    When *cut_marks* is ``True``, hairline crop marks are drawn at every cell
    corner on every output sheet to guide the cutter operator.

    Margin computation
    ------------------
    When the template specifies ``cut_width`` and ``cut_height``, the cell
    size is derived from those dimensions (cut + 2 × bleed) and the grid is
    centred on the sheet automatically.  If the cut-size grid would overflow
    the sheet the template's explicit ``margin_*`` fields are used instead.
    """
    from apps.impose.models import ImpositionTemplate

    lt = template.layout_type
    sheet_w = float(template.sheet_width)
    sheet_h = float(template.sheet_height)
    bleed = float(template.bleed)

    # ── Compute effective margins ──────────────────────────────────────────
    cut_w = float(template.cut_width) if template.cut_width is not None else None
    cut_h = float(template.cut_height) if template.cut_height is not None else None

    if cut_w is not None and cut_h is not None:
        cell_w_size = cut_w + 2 * bleed
        cell_h_size = cut_h + 2 * bleed
        grid_w = template.columns * cell_w_size
        grid_h = template.rows * cell_h_size
        if grid_w <= sheet_w and grid_h <= sheet_h:
            # Centre grid symmetrically on the sheet.
            eff_margin_left = (sheet_w - grid_w) / 2
            eff_margin_right = eff_margin_left
            eff_margin_top = (sheet_h - grid_h) / 2
            eff_margin_bottom = eff_margin_top
        else:
            eff_margin_left = float(template.margin_left)
            eff_margin_right = float(template.margin_right)
            eff_margin_top = float(template.margin_top)
            eff_margin_bottom = float(template.margin_bottom)
    else:
        eff_margin_left = float(template.margin_left)
        eff_margin_right = float(template.margin_right)
        eff_margin_top = float(template.margin_top)
        eff_margin_bottom = float(template.margin_bottom)

    # ── Run the core imposition ────────────────────────────────────────────
    imposed_buf = io.BytesIO()

    if not pages_are_unique or lt == ImpositionTemplate.LayoutType.STEP_REPEAT:
        impose_step_repeat(
            input_pdf,
            imposed_buf,
            columns=template.columns,
            rows=template.rows,
            sheet_width=sheet_w,
            sheet_height=sheet_h,
            bleed=bleed,
        )
    elif is_double_sided:
        impose_double_sided_nup(
            input_pdf,
            imposed_buf,
            columns=template.columns,
            rows=template.rows,
            sheet_width=sheet_w,
            sheet_height=sheet_h,
            bleed=bleed,
            margin_top=eff_margin_top,
            margin_right=eff_margin_right,
            margin_bottom=eff_margin_bottom,
            margin_left=eff_margin_left,
            auto_rotate=auto_rotate,
        )
    elif lt == ImpositionTemplate.LayoutType.BUSINESS_CARD:
        impose_business_card_21up(input_pdf, imposed_buf)
    else:
        impose_nup(
            input_pdf,
            imposed_buf,
            columns=template.columns,
            rows=template.rows,
            sheet_width=sheet_w,
            sheet_height=sheet_h,
            bleed=bleed,
            margin_top=eff_margin_top,
            margin_right=eff_margin_right,
            margin_bottom=eff_margin_bottom,
            margin_left=eff_margin_left,
            auto_rotate=auto_rotate,
        )

    # ── Build overlay content streams (barcode + cut marks) ───────────────
    has_barcode = (
        barcode_value
        and template.barcode_x is not None
        and template.barcode_y is not None
    )

    if not has_barcode and not cut_marks:
        imposed_buf.seek(0)
        output_pdf.write(imposed_buf.read())
        return

    overlay_stream = b""

    if has_barcode:
        bx = float(template.barcode_x)
        by = float(template.barcode_y)
        bw = float(template.barcode_width)
        bh = float(template.barcode_height)
        overlay_stream += _barcode_pdf_stream(barcode_value, bx, by, bw, bh)

    if cut_marks:
        # Re-derive cell trim positions using the same formulas as impose_nup.
        # When all margins are zero impose_nup auto-centres, which is a no-op
        # (grid fills the sheet); the positions here match that behaviour.
        cols = template.columns
        num_rows = template.rows
        cell_w = (sheet_w - eff_margin_left - eff_margin_right) / cols
        cell_h = (sheet_h - eff_margin_top - eff_margin_bottom) / num_rows
        cells = []
        for r in range(num_rows):
            for c in range(cols):
                tl = eff_margin_left + c * cell_w + bleed
                tb = sheet_h - eff_margin_top - (r + 1) * cell_h + bleed
                tw = cell_w - 2 * bleed
                th = cell_h - 2 * bleed
                cells.append((tl, tb, tw, th))
        if overlay_stream:
            overlay_stream += b"\n"
        overlay_stream += _cut_marks_pdf_stream(cells, bleed)

    if not overlay_stream:
        imposed_buf.seek(0)
        output_pdf.write(imposed_buf.read())
        return

    # ── Merge overlay onto every output sheet ─────────────────────────────
    from pypdf import PdfReader, PdfWriter

    imposed_buf.seek(0)
    reader = PdfReader(imposed_buf)
    writer = PdfWriter()

    # Add all pages to the writer first (required by pypdf for reliable merging).
    for page in reader.pages:
        writer.add_page(page)

    overlay_page = _make_overlay_page(sheet_w, sheet_h, overlay_stream)
    for page in writer.pages:
        page.merge_page(overlay_page)

    writer.write(output_pdf)
