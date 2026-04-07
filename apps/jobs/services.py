"""Business logic for job intake and metadata extraction."""

import logging
from pathlib import Path

from core.pdf_utils import extract_pdf_metadata, validate_and_repair_pdf

logger = logging.getLogger(__name__)

__all__ = [
    "compute_fiery_name",
    "extract_pdf_metadata",
    "run_preflight_for_job",
    "validate_and_repair_pdf",
]


def compute_fiery_name(job) -> str:
    """Return the job title as it will appear on the Fiery print queue.

    The title follows the pattern: ``{preset}_{stem}_{barcode}``
    matching what ``process_job_task`` sends via lpr.
    """
    from core.services import get_job_barcode_config

    preset_name = job.routing_preset.name if job.routing_preset else ""
    raw_name = Path(job.name).stem if job.name else f"job-{job.pk}"
    bc = get_job_barcode_config(job)
    barcode_suffix = f"_{bc['barcode_value']}" if bc["barcode_value"] else ""
    if preset_name:
        return f"{preset_name}_{raw_name}{barcode_suffix}"
    return f"{raw_name}{barcode_suffix}"


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

    # If preflight corrected the orientation, overwrite the source file so that
    # the imposition task picks up the rotated version.
    if result.corrected_bytes is not None:
        try:
            from django.core.files.base import ContentFile

            fname = job.file.name.split("/")[-1] if job.file.name else "source.pdf"
            job.file.delete(save=False)
            job.file.save(fname, ContentFile(result.corrected_bytes), save=False)
            job.save(update_fields=["file"])
            logger.info(
                "Replaced source file with orientation-corrected PDF for job %s", job.pk
            )
        except Exception as exc:
            logger.warning(
                "Could not save corrected PDF for job %s: %s", job.pk, exc
            )

    job.preflight_status = result.status
    job.preflight_rules_triggered = result.rules_triggered
    job.preflight_messages = result.messages
    # new field to keep photo name per message (same order)
    job.preflight_images = getattr(result, "images", [])
    job.preflight_notes = result.notes
    job.preflight_acknowledged = False
    job.save(
        update_fields=[
            "preflight_status",
            "preflight_rules_triggered",
            "preflight_messages",
            "preflight_images",
            "preflight_notes",
            "preflight_acknowledged",
        ]
    )
