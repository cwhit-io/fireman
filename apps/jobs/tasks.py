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
            impose_from_template(
                job.imposition_template,
                buf_in,
                buf_out,
                pages_are_unique=job.pages_are_unique,
            )
            buf_out.seek(0)

            imposed_name = f"{job.pk}_imposed.pdf"
            job.imposed_file.save(imposed_name, ContentFile(buf_out.read()), save=True)
            job.status = PrintJob.Status.IMPOSED
            job.save(update_fields=["status"])
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Imposition failed for job %s", job.pk)
            job.status = PrintJob.Status.ERROR
            job.error_message = f"Imposition failed: {exc}"
            job.save(update_fields=["status", "error_message"])
            return

    # ── Step 4: Barcode overlay ───────────────────────────────────────────
    if job.cutter_program_id and job.imposed_file:
        template = job.imposition_template
        if template and template.barcode_x is not None and template.barcode_y is not None:
            try:
                from apps.cutter.services import place_barcode_on_pdf

                buf_in = io.BytesIO()
                with job.imposed_file.open("rb") as fh:
                    buf_in.write(fh.read())
                buf_in.seek(0)

                buf_out = io.BytesIO()
                place_barcode_on_pdf(
                    buf_in,
                    buf_out,
                    job.cutter_program.duplo_code,
                    float(template.barcode_x),
                    float(template.barcode_y),
                    float(template.barcode_width),
                    float(template.barcode_height),
                )
                buf_out.seek(0)

                imposed_name = f"{job.pk}_imposed.pdf"
                job.imposed_file.save(imposed_name, ContentFile(buf_out.read()), save=True)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).exception("Barcode overlay failed for job %s", job.pk)
                job.error_message = f"Barcode overlay failed: {exc}"
                job.save(update_fields=["error_message"])

    # ── Step 5: Send to printer ───────────────────────────────────────────
    if job.routing_preset_id and job.imposed_file:
        import os
        import tempfile

        from apps.routing.services import send_to_fiery_lpr

        job.status = PrintJob.Status.ROUTING
        job.save(update_fields=["status"])
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                with job.imposed_file.open("rb") as fh:
                    tmp.write(fh.read())
                tmp_path = tmp.name

            send_to_fiery_lpr(tmp_path, job.routing_preset)
            job.status = PrintJob.Status.SENT
            job.save(update_fields=["status"])
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Routing failed for job %s", job.pk)
            job.status = PrintJob.Status.ERROR
            job.error_message = f"Routing failed: {exc}"
            job.save(update_fields=["status", "error_message"])
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
