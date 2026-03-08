"""
Barcode TIF preview utilities for the Duplo DC-646 digital cutter.

Barcode images are pre-generated TIF files stored in ``barcodes/NNN.tif``
(where NNN is the zero-padded duplo program code).  This module provides a
helper to serve those TIFs as browser-viewable PNGs for the cutter program
list / form.  Placement on imposed PDFs is handled entirely by
``apps.impose.services`` via the TIF inline-image pipeline.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_barcode_tif_preview(duplo_code: str) -> bytes | None:
    """Return PNG bytes for the barcode TIF matching *duplo_code*.

    Reads ``barcodes/{num:03d}.tif`` from the project root
    (``settings.BASE_DIR``), converts to 8-bit grayscale, and returns PNG
    bytes ready to serve as ``image/png``.

    Returns ``None`` if *duplo_code* is not numeric or the TIF does not exist.
    """
    from django.conf import settings

    try:
        num = int(duplo_code)
    except (TypeError, ValueError):
        logger.warning(
            "duplo_code %r is not numeric; cannot load TIF preview", duplo_code
        )
        return None

    tif_path = Path(settings.BASE_DIR) / "barcodes" / f"{num:03d}.tif"
    if not tif_path.exists():
        logger.warning("Barcode TIF not found: %s", tif_path)
        return None

    try:
        from PIL import Image

        img = Image.open(tif_path).convert("L")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()
    except Exception:
        logger.exception("Failed to read barcode TIF %r", str(tif_path))
        return None
