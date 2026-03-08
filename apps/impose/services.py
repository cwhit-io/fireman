"""
Imposition services — wrap PyPDF to place input pages onto press sheets.
"""

from __future__ import annotations

import io
import logging
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

    The grid is automatically centred on the sheet when all four margins are
    zero (the default).  Explicit margins override centring.

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
    """Repeat a single source page *columns × rows* times (step-and-repeat)."""
    from pypdf import PdfReader

    reader = PdfReader(input_pdf)
    if not reader.pages:
        return

    from pypdf import PdfWriter

    buf = io.BytesIO()
    w = PdfWriter()
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
    auto_rotate: bool = True,
) -> None:
    """Dispatch imposition to the right function based on *template* settings.

    When *pages_are_unique* is ``False`` (step-and-repeat / stack-cut for Duplo),
    the first source page is repeated for every cell on the sheet, regardless of
    the template's ``layout_type``.

    When *auto_rotate* is ``True`` each source page is rotated automatically to
    match the cell orientation so a single template works for both landscape and
    portrait sources.
    """
    from apps.impose.models import ImpositionTemplate

    lt = template.layout_type
    sheet_w = float(template.sheet_width)
    sheet_h = float(template.sheet_height)
    bleed = float(template.bleed)

    # Step-and-repeat / stack-cut: all cells show the same (first) page.
    if not pages_are_unique or lt == ImpositionTemplate.LayoutType.STEP_REPEAT:
        impose_step_repeat(
            input_pdf,
            output_pdf,
            columns=template.columns,
            rows=template.rows,
            sheet_width=sheet_w,
            sheet_height=sheet_h,
            bleed=bleed,
        )
    elif lt == ImpositionTemplate.LayoutType.BUSINESS_CARD:
        impose_business_card_21up(input_pdf, output_pdf)
    else:
        impose_nup(
            input_pdf,
            output_pdf,
            columns=template.columns,
            rows=template.rows,
            sheet_width=sheet_w,
            sheet_height=sheet_h,
            bleed=bleed,
            margin_top=float(template.margin_top),
            margin_right=float(template.margin_right),
            margin_bottom=float(template.margin_bottom),
            margin_left=float(template.margin_left),
            auto_rotate=auto_rotate,
        )
