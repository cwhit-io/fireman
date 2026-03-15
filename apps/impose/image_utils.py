"""
Utilities to convert uploaded JPG/PNG images into single-page PDF bytes.

Usage:
    from apps.impose.image_utils import image_to_pdf_bytes, image_to_contentfile
    pdf_bytes = image_to_pdf_bytes(uploaded_file.read())
    # or, to get a Django ContentFile (for saving to a FileField):
    content_file = image_to_contentfile(uploaded_file.read(), name="converted.pdf")
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps

InputType = bytes | bytearray | BinaryIO | str | Path


def _open_buffer(src: InputType) -> io.BytesIO:
    if isinstance(src, bytes | bytearray):
        return io.BytesIO(src)
    if isinstance(src, str | Path):
        return io.BytesIO(Path(str(src)).read_bytes())
    # assume file-like
    buf = io.BytesIO()
    # if src is already a BytesIO, this will copy its contents correctly
    data = src.read()
    if isinstance(data, str):
        data = data.encode()
    buf.write(data)
    buf.seek(0)
    return buf


def image_to_pdf_bytes(
    src: InputType,
    dpi: int = 300,
    max_width: int = 10000,
    max_height: int = 10000,
    background_color: tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    """
    Convert a JPEG/PNG image (or bytes/file-like) to a single-page PDF.

    - Corrects EXIF orientation.
    - Flattens alpha to a white background.
    - Optionally downsamples oversized images to `max_width`/`max_height`.
    - Returns PDF as bytes.

    Raises ValueError for unsupported/invalid inputs.
    """
    buf = _open_buffer(src)
    try:
        with Image.open(buf) as img:
            img = ImageOps.exif_transpose(img)

            # Reject obviously huge images to avoid OOM; downscale if slightly over.
            w, h = img.size
            if w <= 0 or h <= 0:
                raise ValueError("Invalid image dimensions")

            if w > max_width or h > max_height:
                scale = min(max_width / w, max_height / h)
                new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
                img = img.resize(new_size, Image.LANCZOS)

            # Flatten alpha channels to white background (PDFs are usually RGB).
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                alpha = img.convert("RGBA").split()[-1]
                background = Image.new("RGB", img.size, background_color)
                background.paste(img.convert("RGBA"), mask=alpha)
                img = background
            else:
                img = img.convert("RGB")

            out = io.BytesIO()
            # Pillow's PDF writer will embed the image as a single-page PDF.
            img.save(out, format="PDF", resolution=dpi, quality=95)
            out.seek(0)
            return out.read()
    except Exception as exc:
        raise ValueError(f"Failed to convert image to PDF: {exc}") from exc


def image_to_contentfile(
    src: InputType,
    name: str = "converted.pdf",
    dpi: int = 300,
    max_width: int = 10000,
    max_height: int = 10000,
):
    """
    Convert and return a Django ContentFile if Django is available.

    Returns a `django.core.files.base.ContentFile` or raises ImportError if
    Django is not installed in the current environment.
    """
    pdf_bytes = image_to_pdf_bytes(src, dpi=dpi, max_width=max_width, max_height=max_height)
    try:
        from django.core.files.base import ContentFile

        return ContentFile(pdf_bytes, name=name)
    except Exception as exc:
        raise ImportError("Django not available to create ContentFile") from exc
