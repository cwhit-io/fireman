from celery import shared_task


@shared_task
def process_job_task(job_id: str) -> None:
    """Extract metadata from a newly uploaded job, then apply any matching rules."""
    from .models import PrintJob
    from .services import extract_pdf_metadata

    try:
        job = PrintJob.objects.get(pk=job_id)
    except PrintJob.DoesNotExist:
        return

    job.status = PrintJob.Status.PROCESSING
    job.save(update_fields=["status"])

    extract_pdf_metadata(job)

    if job.status == PrintJob.Status.ERROR:
        return

    # Run the rules engine
    from apps.rules.engine import apply_rules

    apply_rules(job)
