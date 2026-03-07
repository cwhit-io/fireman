"""
Barcode generation for the Duplo DC-646 digital cutter.

The DC-646 reads a QR code printed on the sheet to load the correct
cutting program automatically.
"""
from __future__ import annotations

import io
import logging
from typing import IO

logger = logging.getLogger(__name__)


def generate_qr_barcode(data: str, box_size: int = 10, border: int = 2) -> bytes:
    """Return a PNG byte string containing a QR code for *data*."""
    import qrcode

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def barcode_pdf_snippet(
    data: str,
    x: float,
    y: float,
    size: float = 72.0,
) -> bytes:
    """
    Return a minimal single-page PDF containing a QR barcode placed at (*x*, *y*).

    *x*, *y*, *size* are in PDF points. The page is 1 pt × 1 pt (transparent
    background) so it can be overlaid on the imposed sheet.
    """
    from PIL import Image

    png_bytes = generate_qr_barcode(data)

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    jpeg_buf = io.BytesIO()
    img.save(jpeg_buf, format="JPEG", quality=95)
    jpeg_bytes = jpeg_buf.getvalue()

    pdf_content = _build_image_pdf(jpeg_bytes, img.width, img.height, x, y, size, size)
    return pdf_content


def _build_image_pdf(
    jpeg_bytes: bytes,
    img_w: int,
    img_h: int,
    x: float,
    y: float,
    draw_w: float,
    draw_h: float,
) -> bytes:
    """Build a raw PDF with a single JPEG image placed at (x, y) with size draw_w × draw_h."""

    def num(n):
        return f"{n:.4f}"

    img_len = len(jpeg_bytes)

    xobj = (
        f"<</Type/XObject/Subtype/Image/Width {img_w}/Height {img_h}"
        f"/ColorSpace/DeviceRGB/BitsPerComponent 8"
        f"/Filter/DCTDecode/Length {img_len}>>\n"
        f"stream\n"
    ).encode() + jpeg_bytes + b"\nendstream"

    content_stream = (
        f"q {num(draw_w)} 0 0 {num(draw_h)} {num(x)} {num(y)} cm /Im1 Do Q"
    ).encode()

    objects: list[bytes] = []

    # obj 1: image XObject
    objects.append(xobj)
    # obj 2: content stream
    objects.append(
        f"<</Length {len(content_stream)}>>\nstream\n".encode()
        + content_stream
        + b"\nendstream"
    )
    # obj 3: page
    objects.append(
        b"<</Type/Page/Parent 4 0 R/MediaBox[0 0 612 792]"
        b"/Contents 2 0 R/Resources<</XObject<</Im1 1 0 R>>>>>>"
    )
    # obj 4: pages
    objects.append(b"<</Type/Pages/Kids[3 0 R]/Count 1>>")
    # obj 5: catalog
    objects.append(b"<</Type/Catalog/Pages 4 0 R>>")

    header = b"%PDF-1.4\n"
    body = bytearray(header)
    offsets = []
    for i, obj_data in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode() + obj_data + b"\nendobj\n"

    xref_offset = len(body)
    xref = b"xref\n" + f"0 {len(objects) + 1}\n".encode()
    xref += b"0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()

    trailer = (
        f"trailer\n<</Size {len(objects) + 1}/Root 5 0 R>>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()

    return bytes(body) + xref + trailer


def place_barcode_on_pdf(
    source_pdf: IO[bytes],
    output_pdf: IO[bytes],
    program_code: str,
    x: float,
    y: float,
    size: float = 72.0,
) -> None:
    """
    Overlay a DC-646 QR barcode at (*x*, *y*) on every page of *source_pdf*
    and write the result to *output_pdf*.
    """
    from pypdf import PdfReader, PdfWriter, Transformation

    barcode_pdf_bytes = barcode_pdf_snippet(program_code, x, y, size)
    barcode_reader = PdfReader(io.BytesIO(barcode_pdf_bytes))
    barcode_page = barcode_reader.pages[0]

    reader = PdfReader(source_pdf)
    writer = PdfWriter()
    for page in reader.pages:
        page.merge_transformed_page(barcode_page, Transformation())
        writer.add_page(page)
    writer.write(output_pdf)
