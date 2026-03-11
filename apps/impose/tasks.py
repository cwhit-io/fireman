import io
import logging

from celery import shared_task
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@shared_task
def impose_job_task(job_id: str, template_id: int | None = None) -> None:
    """Run imposition for a job, optionally overriding the template."""
    from apps.impose.models import ImpositionTemplate
    from apps.impose.services import impose_from_template
    from apps.jobs.models import PrintJob
    from core.services import get_job_barcode_config

    try:
        job = PrintJob.objects.get(pk=job_id)
    except PrintJob.DoesNotExist:
        return

    tmpl = job.imposition_template
    if template_id:
        try:
            tmpl = ImpositionTemplate.objects.get(pk=template_id)
        except ImpositionTemplate.DoesNotExist:
            pass

    if not tmpl:
        logger.warning("No imposition template for job %s", job_id)
        return

    job.status = PrintJob.Status.PROCESSING
    job.save(update_fields=["status"])

    try:
        with job.file.open("rb") as fh:
            input_buf = io.BytesIO(fh.read())
        output_buf = io.BytesIO()
        bc = get_job_barcode_config(job)
        impose_from_template(
            tmpl,
            input_buf,
            output_buf,
            pages_are_unique=job.pages_are_unique,
            is_double_sided=job.is_double_sided,
            barcode_value=bc["barcode_value"],
            barcode_x=bc["barcode_x"],
            barcode_y=bc["barcode_y"],
            barcode_width=bc["barcode_width"],
            barcode_height=bc["barcode_height"],
        )
        output_buf.seek(0)
        from pathlib import Path

        stem = Path(job.name).stem if job.name else f"job_{job.pk}"
        barcode_suffix = f"_{bc['barcode_value']}" if bc["barcode_value"] else ""
        fname = f"{stem}{barcode_suffix}_imposed.pdf"
        job.imposed_file.save(fname, ContentFile(output_buf.read()), save=False)
        job.status = PrintJob.Status.IMPOSED
        job.save(update_fields=["imposed_file", "status"])
    except Exception as exc:
        logger.exception("Imposition failed for job %s: %s", job_id, exc)
        job.status = PrintJob.Status.ERROR
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message"])
