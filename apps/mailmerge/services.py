"""
Mail-merge services for USPS Intelligent Mail postcards.

Workflow
--------
1. Parse the USPS CSV file to extract address/IMb records.
2. For each record, copy the artwork PDF page and overlay the address block.
3. Concatenate all pages into a single output PDF.

Address block position (per user spec)
---------------------------------------
- Bottom of address block: 2.5 inches from the bottom of the card.
- Left edge of address block: (card_width - 4.5 inches) from the left.

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

# Address block anchor (inches)
_ADDR_BOTTOM_IN: float = 2.5  # bottom of address block from card bottom
_ADDR_FROM_RIGHT_IN: float = 4.5  # address block left edge = card_width - this

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
) -> bytes:
    """Return a PDF content-stream fragment that draws the address block.

    The stream uses only the built-in Helvetica Type1 font (/F1), which
    requires no font embedding.  The font resource must be declared on the
    page that receives this stream (see ``_make_address_overlay_page``).
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
    x = card_w - _ADDR_FROM_RIGHT_IN * _PT_PER_IN
    y_base = _ADDR_BOTTOM_IN * _PT_PER_IN  # baseline of the lowest line

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
) -> int:
    """Produce a mail-merged PDF with one page per address record.

    Each output page is a copy of the artwork page with the USPS address
    block overlaid in the bottom-right area.

    Parameters
    ----------
    artwork_pdf:
        Readable binary stream of the postcard artwork PDF (single page).
    records:
        Parsed address records from :func:`parse_usps_csv`.
    output_pdf:
        Writable binary stream for the merged output.

    Returns
    -------
    int
        Number of pages written (= number of records processed).
    """
    from pypdf import PdfReader, PdfWriter

    artwork_bytes = artwork_pdf.read()
    if not artwork_bytes:
        raise ValueError("Artwork PDF is empty.")

    artwork_reader = PdfReader(io.BytesIO(artwork_bytes))
    if not artwork_reader.pages:
        raise ValueError("Artwork PDF contains no pages.")

    artwork_page = artwork_reader.pages[0]
    mediabox = artwork_page.mediabox
    card_w = float(mediabox.width)
    card_h = float(mediabox.height)

    writer = PdfWriter()
    pages_written = 0

    for record in records:
        # Clone the artwork page for this recipient
        buf = io.BytesIO(artwork_bytes)
        reader = PdfReader(buf)
        page = reader.pages[0]

        stream = _address_text_stream(record, card_w, card_h)
        if stream:
            overlay = _make_address_overlay_page(card_w, card_h, stream)
            page.merge_page(overlay)

        writer.add_page(page)
        pages_written += 1

    writer.write(output_pdf)
    return pages_written
