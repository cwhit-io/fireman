from celery import shared_task


@shared_task
def process_job_task(job_id: str) -> None:
    """
    Full processing pipeline for a print job:
    1. Extract PDF metadata (page count / size)
    2. Impose the PDF using the assigned template
    3. Send the imposed PDF to the printer (if a routing preset is set)
    """
    import io
    import logging

    from django.core.files.base import ContentFile

    from core.services import get_job_barcode_config

    from .models import PrintJob
    from .services import extract_pdf_metadata

    try:
        job = PrintJob.objects.get(pk=job_id)
    except PrintJob.DoesNotExist:
        return

    job.status = PrintJob.Status.PROCESSING
    job.error_message = ""
    job.save(update_fields=["status", "error_message"])

    extract_pdf_metadata(job)
    if job.status == PrintJob.Status.ERROR:
        return

    # ── Step 2: Imposition ────────────────────────────────────────────────
    if job.imposition_template_id:
        try:
            from apps.impose.services import impose_from_template

            buf_in = io.BytesIO()
            with job.file.open("rb") as fh:
                buf_in.write(fh.read())
            buf_in.seek(0)

            buf_out = io.BytesIO()
            bc = get_job_barcode_config(job)
            impose_from_template(
                job.imposition_template,
                buf_in,
                buf_out,
                pages_are_unique=job.pages_are_unique,
                barcode_value=bc["barcode_value"],
                barcode_x=bc["barcode_x"],
                barcode_y=bc["barcode_y"],
                barcode_width=bc["barcode_width"],
                barcode_height=bc["barcode_height"],
            )
            buf_out.seek(0)

            from pathlib import Path as _Path

            stem = _Path(job.name).stem if job.name else f"job_{job.pk}"
            barcode_suffix = f"_{bc['barcode_value']}" if bc["barcode_value"] else ""
            imposed_name = f"{stem}{barcode_suffix}_imposed.pdf"
            job.imposed_file.save(imposed_name, ContentFile(buf_out.read()), save=True)
            job.status = PrintJob.Status.IMPOSED
            job.save(update_fields=["status"])
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "Imposition failed for job %s", job.pk
            )
            job.status = PrintJob.Status.ERROR
            job.error_message = f"Imposition failed: {exc}"
            job.save(update_fields=["status", "error_message"])
            return

    # ── Step 3: Send to printer ───────────────────────────────────────────
    # Auto-send is disabled. The user must manually press "Send to Printer"
    # on the job details page to submit the imposed PDF to the Fiery.
    pass
