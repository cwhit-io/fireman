"""
Barcode TIF preview utilities for the Duplo DC-646 digital cutter.

Barcode images are pre-generated TIF files stored in ``barcodes/NNN.tif``
(where NNN is the zero-padded duplo program code).  This module provides a
helper to serve those TIFs as browser-viewable PNGs for the cutter program
list / form.  Placement on imposed PDFs is handled entirely by
``apps.impose.services`` via the TIF inline-image pipeline.
"""

from __future__ import annotations

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
        logger.warning("duplo_code %r is not numeric; cannot load TIF preview", duplo_code)
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
            logger.warning("Barcode TIF not found: %s", tif_path)
            return None

    # Cached WebP preview path
    webp_dir = assets_base / "printer" / "barcodes_webp"
    webp_dir.mkdir(parents=True, exist_ok=True)
    webp_path = webp_dir / f"{num:03d}.webp"

    # If cached WebP exists, return it
    if webp_path.exists():
        try:
            return webp_path.read_bytes()
        except Exception:
            logger.exception("Failed to read cached barcode preview %r", str(webp_path))

    # Convert TIFF -> WebP (lossless) and cache
    try:
        from PIL import Image

        img = Image.open(tif_path)
        # Choose a safe convert mode
        if img.mode in ("RGBA", "CMYK"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        img.save(webp_path, format="WEBP", lossless=True, quality=100)
        return webp_path.read_bytes()
    except Exception:
        logger.exception("Failed to convert/read barcode TIF %r", str(tif_path))
        return None
