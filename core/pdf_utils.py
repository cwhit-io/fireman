"""Generic PDF utility functions shared across apps."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def validate_and_repair_pdf(file_field) -> tuple[bytes | None, list[str]]:
    """
    Try to open the PDF, optionally repair it, and return (repaired_bytes, warnings).

    Returns ``(None, warnings)`` if the file is unrecoverable.
    Returns ``(bytes, warnings)`` on success — bytes may be the original content
    or a repaired/re-written copy.
    """
    from io import BytesIO

    warnings: list[str] = []

    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return None, ["pypdf is not installed; cannot validate PDF."]

    # Read original bytes
    try:
        with file_field.open("rb") as fh:
            raw = fh.read()
    except Exception as exc:
        return None, [f"Could not read uploaded file: {exc}"]

    # First try strict parsing
    try:
        reader = PdfReader(BytesIO(raw), strict=True)
        _ = len(reader.pages)  # force full parse
        return raw, warnings  # PDF is clean
    except Exception:
        pass  # fall through to lenient repair

    # Try lenient parsing
    try:
        reader = PdfReader(BytesIO(raw), strict=False)
        page_count = len(reader.pages)
        if page_count == 0:
            return None, ["PDF contains no pages and could not be repaired."]

        # Re-write through PdfWriter to produce a clean file
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        buf = BytesIO()
        writer.write(buf)
        warnings.append(
            "The uploaded PDF had minor errors and was automatically repaired."
        )
        return buf.getvalue(), warnings
    except Exception as exc:
        logger.warning("PDF repair failed: %s", exc)
        return None, [f"The uploaded PDF could not be read or repaired: {exc}"]


def extract_pdf_metadata(job) -> None:
    """Read page count and page size from the uploaded PDF and save them to *job*."""
    try:
        from pypdf import PdfReader

        with job.file.open("rb") as fh:
            reader = PdfReader(fh)
            job.page_count = len(reader.pages)
            if reader.pages:
                page = reader.pages[0]
                mb = page.mediabox
                job.page_width = float(mb.width)
                job.page_height = float(mb.height)
        job.save(update_fields=["page_count", "page_width", "page_height"])
    except Exception as exc:
        logger.exception("Failed to extract PDF metadata for job %s: %s", job.pk, exc)
        job.error_message = str(exc)
        job.status = job.Status.ERROR
        job.save(update_fields=["error_message", "status"])
