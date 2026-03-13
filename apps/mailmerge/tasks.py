import io
import logging

from celery import shared_task
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@shared_task
def process_mail_merge_task(job_id: str) -> None:
    """Run the mail-merge for a MailMergeJob asynchronously."""
    from .models import MailMergeJob
    from .services import merge_postcards, parse_usps_csv

    try:
        job = MailMergeJob.objects.get(pk=job_id)
    except MailMergeJob.DoesNotExist:
        logger.error("MailMergeJob %s not found", job_id)
        return

    job.status = MailMergeJob.Status.PROCESSING
    job.error_message = ""
    job.save(update_fields=["status", "error_message"])

    try:
        with job.csv_file.open("rb") as csv_fh:
            records = parse_usps_csv(csv_fh)

        job.record_count = len(records)
        job.save(update_fields=["record_count"])

        if not records:
            raise ValueError("CSV file contains no address records.")

        with job.artwork_file.open("rb") as art_fh:
            artwork_bytes = art_fh.read()

        # Resolve optional address block position
        addr_x_in = float(job.addr_x_in) if job.addr_x_in is not None else None
        addr_y_in = float(job.addr_y_in) if job.addr_y_in is not None else None

        output_buf = io.BytesIO()
        merge_postcards(
            io.BytesIO(artwork_bytes),
            records,
            output_buf,
            merge_page=job.merge_page or 1,
            addr_x_in=addr_x_in,
            addr_y_in=addr_y_in,
        )
        output_buf.seek(0)

        safe_name = job.name or f"mailmerge_{job.pk}"
        output_name = f"{safe_name}_merged.pdf"
        job.output_file.save(output_name, ContentFile(output_buf.read()), save=False)
        job.status = MailMergeJob.Status.DONE
        job.save(update_fields=["output_file", "status"])
    except Exception as exc:
        logger.exception("Mail-merge failed for job %s", job_id)
        job.status = MailMergeJob.Status.ERROR
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message"])
