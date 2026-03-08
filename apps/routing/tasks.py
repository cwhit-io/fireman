import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_job_task(job_id: str) -> None:
    """Send the imposed PDF for a job to the Fiery using its routing preset."""
    from apps.jobs.models import PrintJob
    from apps.routing.services import send_to_fiery_ipp

    try:
        job = PrintJob.objects.get(pk=job_id)
    except PrintJob.DoesNotExist:
        return

    preset = job.routing_preset
    if not preset:
        logger.warning("No routing preset for job %s", job_id)
        return

    pdf_file = job.imposed_file or job.file
    if not pdf_file:
        logger.warning("No PDF file for job %s", job_id)
        return

    job.status = PrintJob.Status.ROUTING
    job.save(update_fields=["status"])

    try:
        raw_name = job.name or f"job-{job.pk}"
        # Strip extension so the Fiery shows e.g. "my_flyer" not "my_flyer.pdf"
        import os

        title = os.path.splitext(raw_name)[0] or raw_name
        send_to_fiery_ipp(pdf_file.path, preset.printer_queue, preset, title=title)
        job.status = PrintJob.Status.SENT
        job.save(update_fields=["status"])
    except Exception as exc:
        logger.exception("Failed to send job %s: %s", job_id, exc)
        job.status = PrintJob.Status.ERROR
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message"])
