import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_job_task(job_id: str, duplex_override: str | None = None) -> None:
    """Send the imposed PDF for a job to the Fiery using its routing preset.

    *duplex_override* (simplex / duplex_long / duplex_short) overrides the
    preset's duplex for this send only.
    """
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
        from pathlib import Path

        preset_name = preset.name
        raw_name = Path(job.name).stem if job.name else f"job-{job.pk}"
        title = f"{preset_name}_{raw_name}"
        logger.info(
            "Sending job %s to %s with title %r", job.pk, preset.printer_queue, title
        )
        send_to_fiery_ipp(
            pdf_file.path,
            preset.printer_queue,
            preset,
            title=title,
            duplex_override=duplex_override,
        )
        job.status = PrintJob.Status.SENT
        job.save(update_fields=["status"])
    except Exception as exc:
        logger.exception("Failed to send job %s: %s", job_id, exc)
        job.status = PrintJob.Status.ERROR
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message"])
