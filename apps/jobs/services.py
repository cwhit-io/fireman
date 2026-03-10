"""Business logic for job intake and metadata extraction."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def compute_fiery_name(job) -> str:
    """Return the job title as it will appear on the Fiery print queue.

    The title follows the pattern: ``{preset}_{stem}_{barcode}``
    matching what ``process_job_task`` sends via lpr.
    """
    preset_name = job.routing_preset.name if job.routing_preset else ""
    raw_name = Path(job.name).stem if job.name else f"job-{job.pk}"
    cp = None
    if job.imposition_template and job.imposition_template.cutter_program_id:
        cp = job.imposition_template.cutter_program
    elif job.cutter_program_id:
        cp = job.cutter_program
    barcode_value = cp.duplo_code if cp else None
    barcode_suffix = f"_{barcode_value}" if barcode_value else ""
    if preset_name:
        return f"{preset_name}_{raw_name}{barcode_suffix}"
    return f"{raw_name}{barcode_suffix}"


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


def run_preflight_for_job(job, pdf_bytes: bytes | None = None) -> None:
    """
    Run preflight checks on *job* and persist the results.

    If *pdf_bytes* is not provided the job's file is opened from storage.
    Trim dimensions are taken from ``job.imposition_template.cut_width/height``.
    If no template or trim dimensions are available, the checks are skipped.
    """
    from .preflight import run_preflight

    trim_w = trim_h = 0.0
    tmpl = job.imposition_template
    if tmpl:
        if tmpl.cut_width and tmpl.cut_height:
            trim_w = float(tmpl.cut_width)
            trim_h = float(tmpl.cut_height)

    if pdf_bytes is None:
        try:
            with job.file.open("rb") as fh:
                pdf_bytes = fh.read()
        except Exception as exc:
            logger.warning("Preflight: could not read file for job %s: %s", job.pk, exc)
            return

    try:
        result = run_preflight(pdf_bytes, trim_w, trim_h)
    except Exception as exc:
        logger.exception("Preflight failed for job %s: %s", job.pk, exc)
        return

    job.preflight_status = result.status
    job.preflight_rules_triggered = result.rules_triggered
    job.preflight_messages = result.messages
    job.preflight_notes = result.notes
    job.preflight_acknowledged = False
    job.save(
        update_fields=[
            "preflight_status",
            "preflight_rules_triggered",
            "preflight_messages",
            "preflight_notes",
            "preflight_acknowledged",
        ]
    )

