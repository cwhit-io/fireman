"""
Mail-merge services for USPS Intelligent Mail postcards.

Workflow
--------
1. Parse the USPS CSV file to extract address/IMb records.
2. For each record, copy the artwork PDF page and overlay the address block.
3. Concatenate all pages into a single output PDF.

Address block position (per user spec)
---------------------------------------
- Bottom of address block: 2.5 inches from the bottom of the card (default).
- Left edge of address block: (card_width - 4.5 inches) from the left (default).
- Both values can be overridden at job creation time via ``addr_x_in`` /
  ``addr_y_in`` (in inches).

Two-page artwork PDFs
---------------------
When the artwork PDF contains exactly two pages (front and address side), the
caller specifies which page receives the address block via ``merge_page``
(1-based).  For each record the output contains **both** pages: the non-address
page is copied as-is and the address page gets the overlay.

Address block line order (bottom → top)
----------------------------------------
1. city-state-zip
2. primary street
3. sec-primary street     (omitted when blank)
4. urbanization           (omitted when blank)
5. company                (omitted when blank)
6. name                   (omitted when blank)
7. imbno                  (USPS Intelligent Mail Barcode number)
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import IO

logger = logging.getLogger(__name__)

# PDF geometry constants
_PT_PER_IN: float = 72.0

# Address block anchor defaults (inches)
_ADDR_BOTTOM_IN_DEFAULT: float = 2.5  # bottom of address block from card bottom
_ADDR_FROM_RIGHT_IN_DEFAULT: float = 4.5  # address block left edge = card_width - this

# Text rendering
_FONT_NAME: bytes = b"/Helvetica"
_FONT_SIZE: float = 9.0
_LINE_HEIGHT: float = 13.0  # points between baselines

# Default address field ordering (bottom → top)
_DEFAULT_FIELDS: list[str] = [
    "city-state-zip",
    "primary street",
    "sec-primary street",
    "urbanization",
    "company",
    "name",
    "imbno",
]

# Barcode
_BARCODE_FIELD: str = "encodedimbno"
_TRAY_FIELD: str = "presorttrayid"
_BARCODE_FONT_SIZE: float = 14.0
_BARCODE_FONT_PATH: str = str(
    Path(__file__).resolve().parent.parent.parent
    / "fonts"
    / "usps"
    / "trueType"
    / "USPSIMBStandard.ttf"
)
# Module-level cache to avoid re-registering the same reportlab font in a process
_rl_registered_fonts: set[str] = set()


def parse_usps_csv(csv_file: IO[bytes]) -> list[dict[str, str]]:
    """Parse a USPS Intelligent Mail CSV file and return a list of row dicts.

    Expected columns (case-insensitive, stripped):
        no, name, contactid, company, urbanization, sec-primary street,
        primary street, city-state-zip, ase, oel, presorttrayid, presortdate,
        imbno, encodedimbno, primary city, primary state, primary zip
    """
    try:
        raw = csv_file.read()
    except Exception:
        raw = csv_file  # already bytes-like

    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = raw

    reader = csv.DictReader(io.StringIO(text))
    # Normalise header names: strip whitespace, lower-case
    records = []
    for row in reader:
        records.append({k.strip().lower(): (v or "").strip() for k, v in row.items()})
    return records


def inspect_artwork_pdf(artwork_pdf: IO[bytes]) -> dict:
    """Return basic metadata about an artwork PDF without modifying it.

    Returns a dict with keys:
        page_count (int): number of pages
        pages (list[dict]): per-page width/height in points and inches
    """
    from pypdf import PdfReader

    artwork_bytes = artwork_pdf.read()
    if not artwork_bytes:
        return {"page_count": 0, "pages": []}

    try:
        reader = PdfReader(io.BytesIO(artwork_bytes))
    except Exception:
        return {"page_count": 0, "pages": []}

    pages = []
    for page in reader.pages:
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        pages.append(
            {
                "width_pt": w,
                "height_pt": h,
                "width_in": round(w / _PT_PER_IN, 4),
                "height_in": round(h / _PT_PER_IN, 4),
            }
        )
    return {"page_count": len(pages), "pages": pages}


def _escape_pdf_string(text: str) -> bytes:
    """Escape a string for use inside a PDF literal string ``(…)``."""
    out = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == "(":
            out.append("\\(")
        elif ch == ")":
            out.append("\\)")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\n":
            out.append("\\n")
        else:
            # Encode to Latin-1; replace unrepresentable chars with '?'
            try:
                ch.encode("latin-1")
                out.append(ch)
            except (UnicodeEncodeError, ValueError):
                out.append("?")
    return "".join(out).encode("latin-1", errors="replace")


def _barcode_slot(
    record: dict[str, str],
    fields: list[str],
) -> tuple[str, int] | None:
    """Return ``(barcode_text, slot_index)`` for the barcode field, or ``None``.

    ``slot_index`` is the 0-based sequential position among **non-empty** fields
    (same basis used to compute Y offsets in the address block).
    """
    if _BARCODE_FIELD not in fields:
        return None
    barcode_text = record.get(_BARCODE_FIELD, "").strip()
    if not barcode_text:
        return None
    slot = 0
    for f in fields:
        if not record.get(f, "").strip():
            continue
        if f == _BARCODE_FIELD:
            return (barcode_text, slot)
        slot += 1
    return None


def _make_barcode_overlay(
    page_w: float,
    page_h: float,
    barcodes: list[tuple[str, float, float]],
    font_path: str | None = None,
    font_size: float | None = None,
):
    """Return a transparent pypdf page with USPS IMb barcodes rendered via reportlab.

    Parameters
    ----------
    page_w, page_h:
        Dimensions of the target page in points (must match the page being overlaid).
    barcodes:
        List of ``(text, x, y)`` tuples — one per barcode to draw.  ``x``/``y``
        are in PDF points (origin at bottom-left), matching the coordinate system
        used throughout the address block rendering.
    font_path:
        Path to the USPSIMBStandard TrueType font file.  Defaults to the bundled
        font at ``fonts/usps/trueType/USPSIMBStandard.ttf``.
    font_size:
        Point size for the barcode font.  Defaults to :data:`_BARCODE_FONT_SIZE`.
    """
    effective_barcodes = [(t, x, y) for t, x, y in barcodes if t.strip()]
    if not effective_barcodes:
        return None

    effective_font_path = font_path or _BARCODE_FONT_PATH
    effective_font_size = font_size if font_size is not None else _BARCODE_FONT_SIZE
    font_alias = "USPSIMBStandard"

    try:
        from pypdf import PdfReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas as rl_canvas

        if font_alias not in _rl_registered_fonts:
            pdfmetrics.registerFont(TTFont(font_alias, effective_font_path))
            _rl_registered_fonts.add(font_alias)

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))
        c.setFont(font_alias, effective_font_size)
        for text, x, y in effective_barcodes:
            c.drawString(x, y, text)
        c.save()
        buf.seek(0)
        return PdfReader(buf).pages[0]
    except Exception:
        logger.exception("Barcode overlay generation failed")
        return None


def _address_text_stream(
    record: dict[str, str],
    card_w: float,
    card_h: float,
    addr_x: float | None = None,
    addr_y: float | None = None,
    font_name: str | None = None,
    font_size: float | None = None,
    line_height: float | None = None,
    fields: list[str] | None = None,
    tray_x: float | None = None,
    tray_y: float | None = None,
    tray_font_size: float | None = None,
) -> bytes:
    """Return a PDF content-stream fragment that draws the address block.

    The stream uses only a built-in Type1 font (/F1), which requires no font
    embedding.  The font resource must be declared on the page that receives
    this stream (see ``_make_address_overlay_page``).

    Parameters
    ----------
    addr_x:
        X coordinate (points from left) of the address block left edge.
        Defaults to ``card_w - 4.5 * 72``.
    addr_y:
        Y coordinate (points from bottom) of the address block baseline.
        Defaults to ``2.5 * 72``.
    font_name:
        PDF Base font name (e.g. ``"Helvetica-Bold"``). Defaults to Helvetica.
    font_size:
        Font size in points. Defaults to ``_FONT_SIZE``.
    line_height:
        Baseline-to-baseline spacing in points. Defaults to ``_LINE_HEIGHT``.
    fields:
        Ordered list of CSV keys to render (bottom → top). Defaults to
        ``_DEFAULT_FIELDS``.
    tray_x, tray_y:
        Absolute position (points) for the ``presorttrayid`` field independent
        of the address block.  When set, the tray field is removed from the
        slot-based flow and rendered at this fixed position instead.
    tray_font_size:
        Font size (points) for the tray ID.  Defaults to *font_size*.
    """
    effective_font_name = f"/{font_name}".encode() if font_name else _FONT_NAME
    effective_font_size = font_size if font_size is not None else _FONT_SIZE
    effective_line_height = line_height if line_height is not None else _LINE_HEIGHT
    effective_fields = fields if fields else _DEFAULT_FIELDS

    tray_separate = tray_x is not None and tray_y is not None
    tray_val: str = ""

    # ── Build address lines with slot-based y-offsets ─────────────────────
    # encodedimbno is always handled via a separate TrueType overlay.
    # presorttrayid is handled via its own absolute position when tray_x/tray_y
    # are set; otherwise it falls through to normal slot-based rendering.
    # Neither special field contributes to the slot index of the others.
    text_slot_lines: list[tuple[int, str]] = []
    slot = 0
    for f in effective_fields:
        val = record.get(f, "").strip()
        if not val:
            continue
        if f == _BARCODE_FIELD:
            # Always rendered via TrueType overlay — never in this stream
            continue
        if f == _TRAY_FIELD and tray_separate:
            tray_val = val
            continue
        text_slot_lines.append((slot, val))
        slot += 1

    if not text_slot_lines and not (tray_separate and tray_val):
        return b""

    # ── Compute anchor position ─────────────────────────────────────────
    if addr_x is None:
        addr_x = card_w - _ADDR_FROM_RIGHT_IN_DEFAULT * _PT_PER_IN
    if addr_y is None:
        addr_y = _ADDR_BOTTOM_IN_DEFAULT * _PT_PER_IN

    x = addr_x
    y_base = addr_y  # baseline of the lowest line

    # ── Build the PDF text content stream ───────────────────────────────
    parts: list[bytes] = [
        b"BT",
        effective_font_name + f" {effective_font_size:.1f} Tf".encode(),
    ]

    for slot_idx, line in text_slot_lines:
        y = y_base + slot_idx * effective_line_height
        escaped = _escape_pdf_string(line)
        parts.append(f"{x:.3f} {y:.3f} Td".encode())
        parts.append(b"(" + escaped + b") Tj")
        # Reset Td so the next iteration specifies an absolute position
        # by undoing the current translation before the next Td.
        parts.append(f"{-x:.3f} {-y:.3f} Td".encode())

    # ── Tray ID at independent absolute position ─────────────────────────
    if tray_separate and tray_val:
        eff_tray_fs = (
            tray_font_size if tray_font_size is not None else effective_font_size
        )
        if eff_tray_fs != effective_font_size:
            parts.append(effective_font_name + f" {eff_tray_fs:.1f} Tf".encode())
        escaped_tray = _escape_pdf_string(tray_val)
        parts.append(f"{tray_x:.3f} {tray_y:.3f} Td".encode())
        parts.append(b"(" + escaped_tray + b") Tj")
        parts.append(f"{-tray_x:.3f} {-tray_y:.3f} Td".encode())

    parts.append(b"ET")
    return b"\n".join(parts)


def _make_address_overlay_page(
    card_w: float,
    card_h: float,
    stream_bytes: bytes,
    font_name: str | None = None,
):
    """Create a transparent PDF page carrying the address text stream.

    The page declares the chosen built-in Type1 font as /F1 in its resource
    dictionary so the text stream can reference it without embedding any data.
    """
    from pypdf import PageObject, PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
    )

    base_font = f"/{font_name}" if font_name else "/Helvetica"
    font_dict = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject(base_font),
        }
    )
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): font_dict,
                }
            )
        }
    )

    page = PageObject.create_blank_page(width=card_w, height=card_h)
    page[NameObject("/Resources")] = resources

    stream_obj = DecodedStreamObject()
    stream_obj.set_data(stream_bytes)
    page[NameObject("/Contents")] = stream_obj

    writer = PdfWriter()
    writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)

    from pypdf import PdfReader

    return PdfReader(buf).pages[0]


def compute_gangup_grid(
    card_w_pt: float,
    card_h_pt: float,
    sheet_w_pt: float = 864.0,  # 12"
    sheet_h_pt: float = 1296.0,  # 18"
) -> tuple[int, int]:
    """Return (columns, rows) that maximise per-sheet card count on the given sheet.

    Both orientations (upright and rotated 90°) are considered and the one
    that places more cards per sheet is chosen.
    """
    if card_w_pt <= 0 or card_h_pt <= 0:
        return 1, 1

    # Normal orientation
    cols_n = max(1, int(sheet_w_pt / card_w_pt))
    rows_n = max(1, int(sheet_h_pt / card_h_pt))

    # Rotated 90° orientation
    cols_r = max(1, int(sheet_w_pt / card_h_pt))
    rows_r = max(1, int(sheet_h_pt / card_w_pt))

    if cols_r * rows_r > cols_n * rows_n:
        return cols_r, rows_r
    return cols_n, rows_n


def build_artwork_gangup(
    artwork_pdf: IO[bytes],
    cols: int,
    rows: int,
    sheet_w_pt: float,
    sheet_h_pt: float,
    output_pdf: IO[bytes],
) -> None:
    """Produce an N-up gang-up press sheet from the artwork PDF.

    Single-page artwork: tile the one design *cols × rows* times per sheet.
    Two-page artwork: produce two sheets — sheet 1 has *cols × rows* copies of
    page 1 (front) and sheet 2 has *cols × rows* copies of page 2 (address side).
    This layout can be duplexed on a press so fronts and backs align.
    """
    from pypdf import PdfReader, PdfWriter

    artwork_bytes = artwork_pdf.read()
    reader = PdfReader(io.BytesIO(artwork_bytes))
    if not reader.pages:
        return

    per_sheet = cols * rows
    final_writer = PdfWriter()

    for src_page in reader.pages:
        # Build a temporary PDF with per_sheet copies of this page.
        tmp_buf = io.BytesIO()
        tmp_w = PdfWriter()
        for _ in range(per_sheet):
            tmp_w.add_page(src_page)
        tmp_w.write(tmp_buf)
        tmp_buf.seek(0)

        sheet_buf = io.BytesIO()
        _impose_nup_simple(
            tmp_buf,
            sheet_buf,
            cols,
            rows,
            sheet_w_pt,
            sheet_h_pt,
        )
        sheet_buf.seek(0)
        for page in PdfReader(sheet_buf).pages:
            final_writer.add_page(page)

    final_writer.write(output_pdf)


def _impose_nup_simple(
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
    columns: int,
    rows: int,
    sheet_w: float,
    sheet_h: float,
) -> None:
    """Minimal N-up imposition: tile source pages onto press sheets.

    Pages are placed sequentially left-to-right, top-to-bottom.  Each source
    page is scaled to fit its cell uniformly (aspect-ratio preserved) and
    centred within the cell.  The grid is centred on the sheet.
    """
    from pypdf import PageObject, PdfReader, PdfWriter, Transformation

    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    pages = list(reader.pages)
    if not pages:
        return

    per_sheet = columns * rows
    cell_w = sheet_w / columns
    cell_h = sheet_h / rows

    for sheet_start in range(0, len(pages), per_sheet):
        sheet = PageObject.create_blank_page(width=sheet_w, height=sheet_h)
        for idx in range(per_sheet):
            page_idx = sheet_start + idx
            if page_idx >= len(pages):
                break
            src = pages[page_idx]

            col = idx % columns
            row = idx // columns

            src_w = float(src.mediabox.width)
            src_h = float(src.mediabox.height)
            src_left = float(src.mediabox.left)
            src_bottom = float(src.mediabox.bottom)

            # Try both orientations and pick the one that fills the cell better.
            scale_n = min(cell_w / src_w, cell_h / src_h) if src_w and src_h else 1.0
            scale_r = min(cell_w / src_h, cell_h / src_w) if src_w and src_h else 1.0
            rotated = scale_r > scale_n
            scale = scale_r if rotated else scale_n

            # Bottom-left corner of the cell on the sheet.
            cell_left = col * cell_w
            cell_bottom = sheet_h - (row + 1) * cell_h

            if rotated:
                # 90° CW: effective dims become src_h × src_w after rotation
                placed_w = src_h * scale
                placed_h = src_w * scale
                center_x = (cell_w - placed_w) / 2
                center_y = (cell_h - placed_h) / 2
                target_left = cell_left + center_x
                target_bottom = cell_bottom + center_y
                tx = target_left - scale * src_bottom
                ty = target_bottom + scale * (src_left + src_w)
                transform = Transformation(ctm=(0, -scale, scale, 0, tx, ty))
            else:
                placed_w = src_w * scale
                placed_h = src_h * scale
                center_x = (cell_w - placed_w) / 2
                center_y = (cell_h - placed_h) / 2
                target_left = cell_left + center_x
                target_bottom = cell_bottom + center_y
                tx = target_left - scale * src_left
                ty = target_bottom - scale * src_bottom
                transform = Transformation().scale(scale).translate(tx, ty)

            sheet.merge_transformed_page(src, transform)

        writer.add_page(sheet)

    writer.write(output_pdf)


def build_address_steprepeat(
    records: list[dict[str, str]],
    card_w: float,
    card_h: float,
    cols: int,
    rows: int,
    sheet_w: float,
    sheet_h: float,
    addr_x: float | None,
    addr_y: float | None,
    output_pdf: IO[bytes],
    font_name: str | None = None,
    font_size: float | None = None,
    line_height: float | None = None,
    fields: list[str] | None = None,
    barcode_font_size: float | None = None,
) -> int:
    """Produce a step-and-repeat PDF containing only address blocks (no artwork).

    Each output sheet holds *cols × rows* address blocks placed in the same
    grid positions as the corresponding artwork tiles in the gang-up sheet.
    The first sheet contains records 1…(cols*rows), the second sheet has the
    next batch, and so on.

    The function does **not** scale the address blocks — they are written at
    the same point size as in ``merge_postcards``, placed at the card-relative
    position converted to sheet coordinates.

    Returns the number of records written.
    """
    from pypdf import PageObject, PdfWriter

    effective_font_size = font_size if font_size is not None else _FONT_SIZE
    effective_line_height = line_height if line_height is not None else _LINE_HEIGHT
    effective_fields = fields if fields else _DEFAULT_FIELDS

    if addr_x is None:
        addr_x = card_w - _ADDR_FROM_RIGHT_IN_DEFAULT * _PT_PER_IN
    if addr_y is None:
        addr_y = _ADDR_BOTTOM_IN_DEFAULT * _PT_PER_IN

    per_sheet = cols * rows
    cell_w = sheet_w / cols
    cell_h = sheet_h / rows

    writer = PdfWriter()

    for sheet_start in range(0, len(records), per_sheet):
        sheet = PageObject.create_blank_page(width=sheet_w, height=sheet_h)

        # Collect all text streams for this sheet into one combined stream.
        combined_parts: list[bytes] = []
        # Collect barcode positions for this sheet (rendered separately via reportlab)
        sheet_barcodes: list[tuple[str, float, float]] = []

        for idx in range(per_sheet):
            rec_idx = sheet_start + idx
            if rec_idx >= len(records):
                break
            record = records[rec_idx]

            col = idx % cols
            row = idx // cols

            # Determine scale so card fits cell (same logic as _impose_nup_simple).
            scale_n = (
                min(cell_w / card_w, cell_h / card_h) if card_w and card_h else 1.0
            )
            scale_r = (
                min(cell_w / card_h, cell_h / card_w) if card_w and card_h else 1.0
            )
            rotated = scale_r > scale_n
            scale = scale_r if rotated else scale_n

            cell_left = col * cell_w
            cell_bottom = sheet_h - (row + 1) * cell_h

            if rotated:
                placed_h = card_w * scale
                center_y = (cell_h - placed_h) / 2
                target_bottom = cell_bottom + center_y
                placed_w = card_h * scale
                center_x = (cell_w - placed_w) / 2
                target_left = cell_left + center_x
                sheet_addr_x = target_left + addr_y * scale
                sheet_addr_y = (
                    target_bottom + (card_w - addr_x - effective_font_size) * scale
                )
            else:
                placed_w = card_w * scale
                placed_h = card_h * scale
                center_x = (cell_w - placed_w) / 2
                center_y = (cell_h - placed_h) / 2
                target_left = cell_left + center_x
                target_bottom = cell_bottom + center_y
                sheet_addr_x = target_left + addr_x * scale
                sheet_addr_y = target_bottom + addr_y * scale

            # Build text lines with slot-based y-offsets (barcode slot preserved).
            text_slot_lines: list[tuple[int, str]] = []
            slot = 0
            for f in effective_fields:
                val = record.get(f, "").strip()
                if not val:
                    continue
                if f == _BARCODE_FIELD:
                    # Collect barcode for separate TrueType overlay
                    b_y = sheet_addr_y + slot * effective_line_height
                    sheet_barcodes.append((val, sheet_addr_x, b_y))
                else:
                    text_slot_lines.append((slot, val))
                slot += 1

            if not text_slot_lines:
                continue

            eff_fn = f"/{font_name}".encode() if font_name else _FONT_NAME
            parts: list[bytes] = [
                b"BT",
                eff_fn + f" {effective_font_size:.1f} Tf".encode(),
            ]
            for slot_idx, line in text_slot_lines:
                y = sheet_addr_y + slot_idx * effective_line_height
                escaped = _escape_pdf_string(line)
                parts.append(f"{sheet_addr_x:.3f} {y:.3f} Td".encode())
                parts.append(b"(" + escaped + b") Tj")
                parts.append(f"{-sheet_addr_x:.3f} {-y:.3f} Td".encode())
            parts.append(b"ET")
            combined_parts.extend(parts)

        if combined_parts:
            _apply_text_stream_to_page(
                sheet, b"\n".join(combined_parts), font_name=font_name
            )

        # Apply barcode overlay for this sheet
        if sheet_barcodes:
            barcode_overlay = _make_barcode_overlay(
                sheet_w,
                sheet_h,
                sheet_barcodes,
                font_size=barcode_font_size,
            )
            if barcode_overlay:
                sheet.merge_page(barcode_overlay)

        writer.add_page(sheet)

    writer.write(output_pdf)
    return len(records)


def _apply_text_stream_to_page(
    page, stream_bytes: bytes, font_name: str | None = None
) -> None:
    """Attach a PDF text content stream to *page* in-place, declaring /F1 font."""
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
    )

    base_font = f"/{font_name}" if font_name else "/Helvetica"
    font_dict = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject(base_font),
        }
    )
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): font_dict,
                }
            )
        }
    )
    page[NameObject("/Resources")] = resources

    stream_obj = DecodedStreamObject()
    stream_obj.set_data(stream_bytes)
    page[NameObject("/Contents")] = stream_obj


def merge_postcards(
    artwork_pdf: IO[bytes],
    records: list[dict[str, str]],
    output_pdf: IO[bytes],
    merge_page: int = 1,
    addr_x_in: float | None = None,
    addr_y_in: float | None = None,
    font_name: str | None = None,
    font_size: float | None = None,
    line_height: float | None = None,
    fields: list[str] | None = None,
    barcode_font_size: float | None = None,
    barcode_x_in: float | None = None,
    barcode_y_in: float | None = None,
    tray_x_in: float | None = None,
    tray_y_in: float | None = None,
    tray_font_size: float | None = None,
) -> int:
    """Produce a mail-merged PDF with one (or two) pages per address record.

    For single-page artwork, each output page is a copy of the artwork page
    with the USPS address block overlaid.

    For two-page artwork (front + address side), each output record produces
    two pages: the non-address page is copied verbatim and the address page
    receives the overlay.  The output order matches the artwork page order.

    Parameters
    ----------
    artwork_pdf:
        Readable binary stream of the postcard artwork PDF (1 or 2 pages).
    records:
        Parsed address records from :func:`parse_usps_csv`.
    output_pdf:
        Writable binary stream for the merged output.
    merge_page:
        1-based page number within the artwork that should receive the address
        block.  Ignored for single-page artwork (always page 1).
    addr_x_in:
        Left edge of the address block in inches from the card's left edge.
        ``None`` uses the default (card_width - 4.5 in).
    addr_y_in:
        Bottom baseline of the address block in inches from the card's bottom.
        ``None`` uses the default (2.5 in).

    Returns
    -------
    int
        Number of *records* processed (not total pages written).
    """
    from pypdf import PdfReader, PdfWriter

    artwork_bytes = artwork_pdf.read()
    if not artwork_bytes:
        raise ValueError("Artwork PDF is empty.")

    artwork_reader = PdfReader(io.BytesIO(artwork_bytes))
    if not artwork_reader.pages:
        raise ValueError("Artwork PDF contains no pages.")

    num_artwork_pages = len(artwork_reader.pages)

    # Clamp merge_page to valid range
    merge_page = max(1, min(merge_page, num_artwork_pages))
    merge_page_idx = merge_page - 1  # 0-based

    # Resolve address block anchor in points
    addr_x_pt = addr_x_in * _PT_PER_IN if addr_x_in is not None else None
    addr_y_pt = addr_y_in * _PT_PER_IN if addr_y_in is not None else None

    # Dimensions of the address page
    addr_page_media = artwork_reader.pages[merge_page_idx].mediabox
    card_w = float(addr_page_media.width)
    card_h = float(addr_page_media.height)

    writer = PdfWriter()
    pages_written = 0

    # Pre-compute effective rendering params (needed for barcode position)
    effective_fields_val = fields if fields else _DEFAULT_FIELDS
    effective_line_height_val = line_height if line_height is not None else _LINE_HEIGHT
    eff_addr_x = (
        addr_x_pt
        if addr_x_pt is not None
        else (card_w - _ADDR_FROM_RIGHT_IN_DEFAULT * _PT_PER_IN)
    )
    eff_addr_y = (
        addr_y_pt if addr_y_pt is not None else (_ADDR_BOTTOM_IN_DEFAULT * _PT_PER_IN)
    )

    for record in records:
        for page_idx in range(num_artwork_pages):
            # Re-read the artwork for each page/record to get a fresh copy
            reader = PdfReader(io.BytesIO(artwork_bytes))
            page = reader.pages[page_idx]

            if page_idx == merge_page_idx:
                stream = _address_text_stream(
                    record,
                    card_w,
                    card_h,
                    addr_x=addr_x_pt,
                    addr_y=addr_y_pt,
                    font_name=font_name,
                    font_size=font_size,
                    line_height=line_height,
                    fields=fields,
                )
                if stream:
                    overlay = _make_address_overlay_page(
                        card_w, card_h, stream, font_name=font_name
                    )
                    page.merge_page(overlay)

                # Barcode overlay (TrueType via reportlab)
                barcode_info = _barcode_slot(record, effective_fields_val)
                if barcode_info:
                    btext, bslot = barcode_info
                    b_y = eff_addr_y + bslot * effective_line_height_val
                    b_overlay = _make_barcode_overlay(
                        card_w,
                        card_h,
                        [(btext, eff_addr_x, b_y)],
                        font_size=barcode_font_size,
                    )
                    if b_overlay:
                        page.merge_page(b_overlay)

            writer.add_page(page)

        pages_written += 1

    writer.write(output_pdf)
    return pages_written
