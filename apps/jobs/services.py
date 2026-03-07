"""Business logic for job intake and metadata extraction."""

import logging

logger = logging.getLogger(__name__)


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
