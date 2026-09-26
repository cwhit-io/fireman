"""Business logic for job intake and metadata extraction."""

import logging
from pathlib import Path

from core.pdf_utils import extract_pdf_metadata, validate_and_repair_pdf

logger = logging.getLogger(__name__)

__all__ = [
    "compute_fiery_name",
    "extract_pdf_metadata",
    "generate_job_thumbnail",
    "purge_unsaved_jobs",
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
        result = run_preflight(
            pdf_bytes,
            trim_w,
            trim_h,
            fit_mode=getattr(job, "fit_mode", "") or "cover",
        )
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
            logger.warning("Could not save corrected PDF for job %s: %s", job.pk, exc)

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


THUMBNAIL_MAX_PX = 192
_PDFTOPPM_TIMEOUT = 30


def render_pdf_first_page_jpeg(
    pdf_bytes: bytes, max_px: int = THUMBNAIL_MAX_PX
) -> bytes | None:
    """Rasterize page 1 of a PDF to a JPEG using pdftoppm. Returns None on failure."""
    import shutil
    import subprocess
    import tempfile

    if not pdf_bytes:
        return None
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        logger.warning("pdftoppm not found; cannot generate job thumbnails")
        return None

    with tempfile.TemporaryDirectory(prefix="ember-thumb-") as tmp:
        src = Path(tmp) / "in.pdf"
        src.write_bytes(pdf_bytes)
        prefix = Path(tmp) / "thumb"
        try:
            subprocess.run(
                [
                    pdftoppm,
                    "-jpeg",
                    "-f",
                    "1",
                    "-l",
                    "1",
                    "-scale-to",
                    str(max_px),
                    str(src),
                    str(prefix),
                ],
                check=True,
                capture_output=True,
                timeout=_PDFTOPPM_TIMEOUT,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            OSError,
        ) as exc:
            logger.warning("pdftoppm failed: %s", exc)
            return None

        # pdftoppm writes {prefix}-1.jpg (sometimes .jpeg)
        for candidate in prefix.parent.glob(f"{prefix.name}-1.*"):
            data = candidate.read_bytes()
            if data:
                return data
    return None


def generate_job_thumbnail(job) -> bool:
    """Create or replace ``job.thumbnail`` from the original PDF. Returns True on success."""
    from django.core.files.base import ContentFile

    source = job.file if job.file else None
    if source and not source.storage.exists(source.name):
        source = None
    if (
        source is None
        and job.imposed_file
        and job.imposed_file.storage.exists(job.imposed_file.name)
    ):
        source = job.imposed_file
    if not source:
        return False
    try:
        with source.open("rb") as fh:
            pdf_bytes = fh.read()
    except Exception as exc:
        logger.warning("Could not read PDF for thumbnail (job %s): %s", job.pk, exc)
        return False

    jpeg = render_pdf_first_page_jpeg(pdf_bytes)
    if not jpeg:
        return False

    if job.thumbnail:
        try:
            job.thumbnail.delete(save=False)
        except Exception:
            pass
    job.thumbnail.save(f"{job.pk}.jpg", ContentFile(jpeg), save=True)
    return True


def purge_unsaved_jobs(*, days: int = 30, dry_run: bool = False) -> dict:
    """Delete unsaved print jobs older than *days*. Returns a result dict.

    Each job is deleted via ``Model.delete()`` so file-cleanup signals run.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import PrintJob

    cutoff = timezone.now() - timedelta(days=days)
    qs = PrintJob.objects.filter(created_at__lt=cutoff, is_saved=False)
    count = qs.count()
    if dry_run:
        return {"count": count, "deleted": 0, "dry_run": True, "days": days}

    deleted = 0
    for job in qs.iterator():
        job.delete()
        deleted += 1
    return {"count": count, "deleted": deleted, "dry_run": False, "days": days}
