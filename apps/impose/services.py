"""
Imposition services — wrap PyPDF to place input pages onto press sheets.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
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


# ── Barcode TIF helpers ────────────────────────────────────────────────────


def _resolve_barcode_tif(barcode_value: str) -> str | None:
    """Return the absolute path to the pre-generated barcode TIF for *barcode_value*.

    The ``barcodes/`` directory at the project root contains files named
    ``001.tif`` – ``250.tif``.  *barcode_value* is coerced to an integer,
    zero-padded to three digits, and used as the filename stem.

    Returns ``None`` if the value is not numeric or the file does not exist.
    """
    from django.conf import settings

    try:
        num = int(barcode_value)
    except (TypeError, ValueError):
        logger.warning(
            "barcode_value %r is not numeric; cannot resolve TIF", barcode_value
        )
        return None

    # Prefer new assets layout: assets/printer/barcodes/*.tif
    assets_base = Path(getattr(settings, "ASSETS_DIR", settings.BASE_DIR))
    tif_path = assets_base / "printer" / "barcodes" / f"{num:03d}.tif"
    # Fallback to legacy project-root `barcodes/` for backward compatibility
    if not tif_path.exists():
        legacy = Path(settings.BASE_DIR) / "barcodes" / f"{num:03d}.tif"
        if legacy.exists():
            tif_path = legacy
        else:
            logger.warning(
                "Barcode TIF not found: %s (checked assets/printer and legacy barcodes)",
                tif_path,
            )
            return None

    return str(tif_path)


def _barcode_tif_pdf_stream(
    tif_path: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> bytes:
    """Return PDF content-stream bytes that place the barcode TIF at *(x, y)*.

    The image is embedded as a PDF inline image using ASCIIHex encoding so
    the bytes remain safe inside any content stream without risk of false
    ``EI`` marker collisions.  No PDF XObject resource is needed, which
    means the overlay can be combined with cut-mark streams and merged
    reliably using ``_make_overlay_page`` + ``page.merge_page``.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.error("Pillow is required for TIF barcode embedding.")
        return b""

    try:
        img = Image.open(tif_path)
        img = img.convert("L")  # 8-bit grayscale; handles 1-bit / CMYK TIFs
        img_w, img_h = img.size
        raw_bytes = img.tobytes()
    except Exception:
        logger.exception("Failed to open barcode TIF %r", tif_path)
        return b""

    # ASCIIHex-encode so the data is pure ASCII — no false EI matches possible.
    hex_data = raw_bytes.hex().upper().encode()

    return (
        b"q\n"
        + f"{width:.3f} 0 0 {height:.3f} {x:.3f} {y:.3f} cm\n".encode()
        + b"BI\n"
        + f"/W {img_w} /H {img_h} /CS /G /BPC 8 /F /AHx\n".encode()
        + b"ID\n"
        + hex_data
        + b">\nEI\nQ"
    )


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
            cmds.append(f"{hx1:.3f} {cy:.3f} m {hx2:.3f} {cy:.3f} l S".encode())
            # vertical arm
            vy1 = cy + dy * total
            vy2 = cy + dy * (total + length)
            cmds.append(f"{cx:.3f} {vy1:.3f} m {cx:.3f} {vy2:.3f} l S".encode())

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


def _clip_page_content_to_box(
    page,
    clip_x: float,
    clip_y: float,
    clip_w: float,
    clip_h: float,
):
    """Return a copy of *page* whose content is clipped to the given rectangle.

    The rectangle is expressed in the source page's own coordinate space (PDF
    points, Y axis up from the page bottom).  The clip is implemented by
    wrapping the existing content stream in a PDF graphics-state save/restore
    with a rectangular clipping path:

        q
        <clip_x> <clip_y> <clip_w> <clip_h> re W n
        … original content …
        Q

    This prevents any content outside the rectangle (e.g. oversized bleed)
    from being visible after the page is placed on the press sheet, regardless
    of the transformation matrix applied by ``merge_transformed_page``.
    """
    from copy import deepcopy

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    # Work on a shallow copy so we don't mutate the original page object.
    writer = PdfWriter()
    writer.add_page(deepcopy(page))
    clipped = writer.pages[0]

    # Build the clip wrapper around the existing stream bytes.
    existing_stream: bytes
    contents = clipped.get("/Contents")
    if contents is None:
        existing_stream = b""
    elif hasattr(contents, "get_data"):
        existing_stream = contents.get_data()
    else:
        # Array of streams — concatenate them.
        existing_stream = b" ".join(obj.get_object().get_data() for obj in contents)

    clip_cmd = (
        f"{clip_x:.4f} {clip_y:.4f} {clip_w:.4f} {clip_h:.4f} re W n\n"
    ).encode()

    wrapped = b"q\n" + clip_cmd + existing_stream + b"\nQ"

    new_stream = DecodedStreamObject()
    new_stream.set_data(wrapped)
    clipped[NameObject("/Contents")] = new_stream

    # Round-trip through PdfReader so merge_transformed_page gets a proper
    # page object rather than a PdfWriter-internal one.
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
    if (
        margin_top == 0
        and margin_right == 0
        and margin_bottom == 0
        and margin_left == 0
    ):
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

            # Bottom-left corner of the cell's trim area on the sheet.
            cell_trim_left = margin_left + col * cell_w + bleed
            cell_trim_bottom = sheet_height - margin_top - (row + 1) * cell_h + bleed

            # Scale so the source trim *covers* the full bleed cell (aspect-ratio preserved).
            # Artwork fills trim + bleed on all sides; excess beyond bleed is clipped below.
            scale_x = cell_w / src_trim_w if src_trim_w else 1.0
            scale_y = cell_h / src_trim_h if src_trim_h else 1.0
            scale = max(scale_x, scale_y)

            # Centre the scaled artwork within the bleed cell; overflow handled by clip mask.
            center_x = (cell_w - src_trim_w * scale) / 2
            center_y = (cell_h - src_trim_h * scale) / 2

            # Desired position for the source trim's bottom-left corner on the sheet.
            # Origin is the bleed cell's bottom-left corner (cell_trim origin minus bleed).
            target_trim_left = (cell_trim_left - bleed) + center_x
            target_trim_bottom = (cell_trim_bottom - bleed) + center_y

            # Transformation: scale(s) then translate(tx, ty).
            tx = target_trim_left - scale * src_trim_left
            ty = target_trim_bottom - scale * src_trim_bottom

            transform = Transformation().scale(scale).translate(tx, ty)

            # Clip the source page to exactly trim + allowed bleed before merging.
            # This prevents oversized source bleed from overflowing into adjacent cells.
            # The clip box is expressed in source page coordinates (before transformation).
            src_allowed_bleed = bleed / scale if scale else 0.0
            clipped_src = _clip_page_content_to_box(
                src,
                src_trim_left - src_allowed_bleed,
                src_trim_bottom - src_allowed_bleed,
                src_trim_w + 2 * src_allowed_bleed,
                src_trim_h + 2 * src_allowed_bleed,
            )
            sheet.merge_transformed_page(clipped_src, transform)

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
    margin_top: float = 0.0,
    margin_right: float = 0.0,
    margin_bottom: float = 0.0,
    margin_left: float = 0.0,
) -> None:
    """Repeat each source page *columns × rows* times on its own output sheet.

    Every page in *input_pdf* produces one full press sheet with that page
    tiled into every cell.  This handles two distinct scenarios:

    * **Single-design run** — one source page, one output sheet filled with
      copies of that design.
    * **Multi-record run** — N source pages, N output sheets (one per record),
      each sheet filled with copies of that record.  Used for variable-data
      or front-only simplex gang-runs where every record is a separate page.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(input_pdf)
    if not reader.pages:
        return

    per_sheet = columns * rows
    final_writer = PdfWriter()

    for src_page in reader.pages:
        # Build a single-page PDF with per_sheet copies of this source page.
        buf = io.BytesIO()
        w = PdfWriter()
        for _ in range(per_sheet):
            w.add_page(src_page)
        w.write(buf)
        buf.seek(0)

        sheet_buf = io.BytesIO()
        impose_nup(
            buf,
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
        )
        sheet_buf.seek(0)
        for page in PdfReader(sheet_buf).pages:
            final_writer.add_page(page)

    final_writer.write(output_pdf)


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


def get_template_effective_margins(template) -> dict:
    """Return the effective margins and cell geometry for *template*.

    Used by both :func:`impose_from_template` and callers that need to place
    content (e.g. address blocks) at the same cell positions as the imposed
    artwork — so both always use identical layout maths without duplication.

    Returns a dict with keys:
        sheet_w, sheet_h, bleed,
        margin_left, margin_right, margin_top, margin_bottom,
        cols, rows,
        cell_w, cell_h          — per-cell size (includes bleed on both sides)
        cell_trim_w, cell_trim_h — trim area inside bleed
    """
    sheet_w = float(template.sheet_width)
    sheet_h = float(template.sheet_height)
    bleed = float(template.bleed)
    cols = template.columns
    rows = template.rows

    cut_w = float(template.cut_width) if template.cut_width is not None else None
    cut_h = float(template.cut_height) if template.cut_height is not None else None

    if cut_w is not None and cut_h is not None:
        # Cell size is always derived from the physical cut dimensions — these
        # are the blade positions the cutter program expects, so they must never
        # be recalculated from sheet / rows / cols even when the grid overflows.
        cell_w = cut_w + 2 * bleed
        cell_h = cut_h + 2 * bleed
        grid_w = cols * cell_w
        grid_h = rows * cell_h
        if grid_w <= sheet_w and grid_h <= sheet_h:
            margin_left = (sheet_w - grid_w) / 2
            margin_right = margin_left
            margin_top = (sheet_h - grid_h) / 2
            margin_bottom = margin_top
        else:
            # Grid overflows the sheet — anchor at origin with zero margins.
            # The template data (columns/rows) needs to be corrected, but we
            # still honour cut_w/cut_h so cut marks and artwork share the same
            # cell orientation.
            margin_left = margin_right = margin_top = margin_bottom = 0.0
    else:
        margin_left = float(template.margin_left)
        margin_right = float(template.margin_right)
        margin_top = float(template.margin_top)
        margin_bottom = float(template.margin_bottom)
        cell_w = (sheet_w - margin_left - margin_right) / cols
        cell_h = (sheet_h - margin_top - margin_bottom) / rows

    return {
        "sheet_w": sheet_w,
        "sheet_h": sheet_h,
        "bleed": bleed,
        "cols": cols,
        "rows": rows,
        "margin_left": margin_left,
        "margin_right": margin_right,
        "margin_top": margin_top,
        "margin_bottom": margin_bottom,
        "cell_w": cell_w,
        "cell_h": cell_h,
        "cell_trim_w": cell_w - 2 * bleed,
        "cell_trim_h": cell_h - 2 * bleed,
    }


def impose_from_template(
    template,
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
    pages_are_unique: bool = True,
    is_double_sided: bool = False,
    barcode_value: str | None = None,
    barcode_x: float | None = None,
    barcode_y: float | None = None,
    barcode_width: float | None = None,
    barcode_height: float | None = None,
    cut_marks: bool = False,
) -> None:
    """Dispatch imposition to the right function based on *template* settings.

    Modes
    -----
    * ``pages_are_unique=False``:
      step-and-repeat — only the **first** source page is used; every cell on
      every output sheet shows that one design.  Multi-page source PDFs are
      truncated to the first page so that a customer who accidentally submits a
      two-page file still gets a single gang-up sheet.
    * ``is_double_sided=True`` and ``pages_are_unique=True``:
      double-sided n-up — each source page fills one complete output sheet
      (e.g. page 1 × 8-up → sheet 1, page 2 × 8-up → sheet 2) so the job
      can be duplexed correctly.
    * Otherwise: standard sequential n-up — pages are gang-imposed across
      sheets using the template's grid dimensions.

    Post-processing overlays
    ------------------------
    When *barcode_value* is set, the matching TIF barcode is stamped on every
    output sheet.  The position is taken from the explicit *barcode_x* /
    *barcode_y* kwargs first (supplied by the cutter program), falling back to
    the template's own ``barcode_x`` / ``barcode_y`` fields.

    When *cut_marks* is ``True``, hairline crop marks are drawn at every cell
    corner on every output sheet to guide the cutter operator.

    Margin computation
    ------------------
    When the template specifies ``cut_width`` and ``cut_height``, the cell
    size is derived from those dimensions (cut + 2 × bleed) and the grid is
    centred on the sheet automatically.  If the cut-size grid would overflow
    the sheet the template's explicit ``margin_*`` fields are used instead.
    """
    from pypdf import PdfReader, PdfWriter

    layout = get_template_effective_margins(template)
    sheet_w = layout["sheet_w"]
    sheet_h = layout["sheet_h"]
    bleed = layout["bleed"]
    eff_margin_left = layout["margin_left"]
    eff_margin_right = layout["margin_right"]
    eff_margin_top = layout["margin_top"]
    eff_margin_bottom = layout["margin_bottom"]

    # ── Run the core imposition ────────────────────────────────────────────
    imposed_buf = io.BytesIO()

    if not pages_are_unique:
        # Step-and-repeat: for single-sided jobs use only the first source
        # page (guards against accidental multi-page uploads).  For
        # double-sided jobs every source page becomes its own imposed sheet so
        # that front and back are both gang'd up correctly.
        raw = input_pdf.read()
        reader_tmp = PdfReader(io.BytesIO(raw))
        if is_double_sided and len(reader_tmp.pages) > 1:
            src_buf = io.BytesIO(raw)
        else:
            first_page_buf = io.BytesIO()
            if reader_tmp.pages:
                w_tmp = PdfWriter()
                w_tmp.add_page(reader_tmp.pages[0])
                w_tmp.write(first_page_buf)
            first_page_buf.seek(0)
            src_buf = first_page_buf

        impose_step_repeat(
            src_buf,
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
        )
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
        )

    # ── Build overlays (barcode TIF + cut marks) ──────────────────────────
    # Resolve barcode position: explicit kwargs (from cutter program) first,
    # then fall back to whatever the template has configured.
    eff_barcode_x = (
        barcode_x
        if barcode_x is not None
        else (float(template.barcode_x) if template.barcode_x is not None else None)
    )
    eff_barcode_y = (
        barcode_y
        if barcode_y is not None
        else (float(template.barcode_y) if template.barcode_y is not None else None)
    )
    eff_barcode_width = (
        barcode_width if barcode_width is not None else float(template.barcode_width)
    )
    eff_barcode_height = (
        barcode_height if barcode_height is not None else float(template.barcode_height)
    )

    has_barcode = (
        barcode_value
        and eff_barcode_x is not None
        and eff_barcode_y is not None
        and getattr(template, "print_barcode", True)
    )

    if not has_barcode and not cut_marks:
        imposed_buf.seek(0)
        output_pdf.write(imposed_buf.read())
        return

    overlay_stream = b""

    if has_barcode:
        tif_path = _resolve_barcode_tif(barcode_value)
        if tif_path:
            overlay_stream += _barcode_tif_pdf_stream(
                tif_path,
                eff_barcode_x,
                eff_barcode_y,
                eff_barcode_width,
                eff_barcode_height,
            )

    if cut_marks:
        # Use the cell dimensions already computed by get_template_effective_margins
        # so that cut marks always reflect the physical cut size, not a re-derived
        # value that can diverge from the template's cut_width/cut_height.
        cell_w = layout["cell_w"]
        cell_h = layout["cell_h"]
        cells = []
        for r in range(template.rows):
            for c in range(template.columns):
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
    imposed_buf.seek(0)
    reader = PdfReader(imposed_buf)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    overlay_page = _make_overlay_page(sheet_w, sheet_h, overlay_stream)
    for page in writer.pages:
        page.merge_page(overlay_page)

    writer.write(output_pdf)
