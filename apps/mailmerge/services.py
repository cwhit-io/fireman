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


def _address_text_stream(
    record: dict[str, str],
    card_w: float,
    card_h: float,
    addr_x: float | None = None,
    addr_y: float | None = None,
) -> bytes:
    """Return a PDF content-stream fragment that draws the address block.

    The stream uses only the built-in Helvetica Type1 font (/F1), which
    requires no font embedding.  The font resource must be declared on the
    page that receives this stream (see ``_make_address_overlay_page``).

    Parameters
    ----------
    addr_x:
        X coordinate (points from left) of the address block left edge.
        Defaults to ``card_w - 4.5 * 72``.
    addr_y:
        Y coordinate (points from bottom) of the address block baseline.
        Defaults to ``2.5 * 72``.
    """
    # ── Build address lines (bottom → top) ──────────────────────────────
    lines: list[str] = []

    city_state_zip = record.get("city-state-zip", "").strip()
    if city_state_zip:
        lines.append(city_state_zip)

    primary_street = record.get("primary street", "").strip()
    if primary_street:
        lines.append(primary_street)

    sec_primary = record.get("sec-primary street", "").strip()
    if sec_primary:
        lines.append(sec_primary)

    urbanization = record.get("urbanization", "").strip()
    if urbanization:
        lines.append(urbanization)

    company = record.get("company", "").strip()
    if company:
        lines.append(company)

    name = record.get("name", "").strip()
    if name:
        lines.append(name)

    imbno = record.get("imbno", "").strip()
    if imbno:
        lines.append(imbno)

    if not lines:
        return b""

    # ── Compute anchor position ─────────────────────────────────────────
    if addr_x is None:
        addr_x = card_w - _ADDR_FROM_RIGHT_IN_DEFAULT * _PT_PER_IN
    if addr_y is None:
        addr_y = _ADDR_BOTTOM_IN_DEFAULT * _PT_PER_IN

    x = addr_x
    y_base = addr_y  # baseline of the lowest line

    # ── Build the PDF text content stream ───────────────────────────────
    parts: list[bytes] = [b"BT", f"/F1 {_FONT_SIZE:.1f} Tf".encode()]

    for i, line in enumerate(lines):
        y = y_base + i * _LINE_HEIGHT
        escaped = _escape_pdf_string(line)
        parts.append(f"{x:.3f} {y:.3f} Td".encode())
        parts.append(b"(" + escaped + b") Tj")
        # Reset Td so the next iteration specifies an absolute position
        # by undoing the current translation before the next Td.
        parts.append(f"{-x:.3f} {-y:.3f} Td".encode())

    parts.append(b"ET")
    return b"\n".join(parts)


def _make_address_overlay_page(card_w: float, card_h: float, stream_bytes: bytes):
    """Create a transparent PDF page carrying the address text stream.

    The page declares /Helvetica as /F1 in its resource dictionary so
    the text stream can reference it without embedding any font data.
    """
    from pypdf import PageObject, PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
    )

    font_dict = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
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


def merge_postcards(
    artwork_pdf: IO[bytes],
    records: list[dict[str, str]],
    output_pdf: IO[bytes],
    merge_page: int = 1,
    addr_x_in: float | None = None,
    addr_y_in: float | None = None,
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

    for record in records:
        for page_idx in range(num_artwork_pages):
            # Re-read the artwork for each page/record to get a fresh copy
            reader = PdfReader(io.BytesIO(artwork_bytes))
            page = reader.pages[page_idx]

            if page_idx == merge_page_idx:
                stream = _address_text_stream(
                    record, card_w, card_h, addr_x=addr_x_pt, addr_y=addr_y_pt
                )
                if stream:
                    overlay = _make_address_overlay_page(card_w, card_h, stream)
                    page.merge_page(overlay)

            writer.add_page(page)

        pages_written += 1

    writer.write(output_pdf)
    return pages_written
