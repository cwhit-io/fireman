from celery import shared_task


@shared_task
def process_job_task(job_id: str) -> None:
    """
    Full processing pipeline for a print job:
    1. Extract PDF metadata (page count / size)
    2. Apply matching rules (assign template / cutter / preset)
    3. Impose the PDF using the assigned template
    4. Overlay the Code 39 cutter barcode (if a cutter program is set)
    5. Send the imposed PDF to the printer (if a routing preset is set)
    """
    import io

    from django.core.files.base import ContentFile

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

    # Run the rules engine (only if no template assigned yet)
    from apps.rules.engine import apply_rules

    apply_rules(job)
    # Re-load to pick up any FK assignments made by apply_rules
    job.refresh_from_db()

    # ── Step 3: Imposition ────────────────────────────────────────────────
    if job.imposition_template_id:
        try:
            from apps.impose.services import impose_from_template

            buf_in = io.BytesIO()
            with job.file.open("rb") as fh:
                buf_in.write(fh.read())
            buf_in.seek(0)

            buf_out = io.BytesIO()
            cp = job.cutter_program if job.cutter_program_id else None
            barcode_value = cp.duplo_code if cp else None
            barcode_x = float(cp.barcode_x) if cp and cp.barcode_x is not None else None
            barcode_y = float(cp.barcode_y) if cp and cp.barcode_y is not None else None
            barcode_width = float(cp.barcode_width) if cp else None
            barcode_height = float(cp.barcode_height) if cp else None
            impose_from_template(
                job.imposition_template,
                buf_in,
                buf_out,
                pages_are_unique=job.pages_are_unique,
                barcode_value=barcode_value,
                barcode_x=barcode_x,
                barcode_y=barcode_y,
                barcode_width=barcode_width,
                barcode_height=barcode_height,
            )
            buf_out.seek(0)

            from pathlib import Path as _Path

            stem = _Path(job.name).stem if job.name else f"job_{job.pk}"
            imposed_name = f"{stem}_imposed.pdf"
            job.imposed_file.save(imposed_name, ContentFile(buf_out.read()), save=True)
            job.status = PrintJob.Status.IMPOSED
            job.save(update_fields=["status"])
        except Exception as exc:
            import logging

            logging.getLogger(__name__).exception(
                "Imposition failed for job %s", job.pk
            )
            job.status = PrintJob.Status.ERROR
            job.error_message = f"Imposition failed: {exc}"
            job.save(update_fields=["status", "error_message"])
            return

    # ── Step 4: Send to printer ───────────────────────────────────────────
    if job.routing_preset_id and job.imposed_file:
        import os
        import tempfile

        from apps.routing.services import send_to_fiery_lpr

        job.status = PrintJob.Status.ROUTING
        job.save(update_fields=["status"])
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                with job.imposed_file.open("rb") as fh:
                    tmp.write(fh.read())
                tmp_path = tmp.name

            from pathlib import Path as _Path

            preset_name = job.routing_preset.name if job.routing_preset else "preset"
            raw_name = _Path(job.name).stem if job.name else f"job-{job.pk}"
            job_title = f"{preset_name}_{raw_name}"
            send_to_fiery_lpr(tmp_path, job.routing_preset, title=job_title)
            job.status = PrintJob.Status.SENT
            job.save(update_fields=["status"])
        except Exception as exc:
            import logging

            logging.getLogger(__name__).exception("Routing failed for job %s", job.pk)
            job.status = PrintJob.Status.ERROR
            job.error_message = f"Routing failed: {exc}"
            job.save(update_fields=["status", "error_message"])
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
