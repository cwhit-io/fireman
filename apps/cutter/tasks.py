import io
import logging

from celery import shared_task
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@shared_task
def add_barcode_task(job_id: str) -> None:
    """Overlay DC-646 barcode on the imposed file for a job."""
    from apps.cutter.services import place_barcode_on_pdf
    from apps.jobs.models import PrintJob

    try:
        job = PrintJob.objects.get(pk=job_id)
    except PrintJob.DoesNotExist:
        return

    if not job.imposed_file or not job.cutter_program:
        return

    try:
        tmpl = job.imposition_template
        x = float(tmpl.barcode_x) if tmpl and tmpl.barcode_x else 36.0
        y = float(tmpl.barcode_y) if tmpl and tmpl.barcode_y else 36.0

        with job.imposed_file.open("rb") as fh:
            input_buf = io.BytesIO(fh.read())
        output_buf = io.BytesIO()
        place_barcode_on_pdf(
            input_buf, output_buf,
            program_code=job.cutter_program.duplo_code,
            x=x,
            y=y,
        )
        output_buf.seek(0)
        fname = f"barcoded_{job.pk}.pdf"
        job.imposed_file.save(fname, ContentFile(output_buf.read()), save=True)
    except Exception as exc:
        logger.exception("Barcode overlay failed for job %s: %s", job_id, exc)
        job.status = PrintJob.Status.ERROR
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message"])
