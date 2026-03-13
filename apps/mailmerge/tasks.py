import io
import logging

from celery import shared_task
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@shared_task
def process_mail_merge_task(job_id: str) -> None:
    """Run the mail-merge for a MailMergeJob asynchronously.

    Produces three output files:
    1. ``output_file`` — merged PDF (one or two pages per recipient).
    2. ``gangup_file`` — artwork gang-up press sheet (N-up, for Fiery master).
    3. ``address_pdf_file`` — address step-and-repeat PDF (one sheet per N records).
    """
    from .models import MailMergeJob
    from .services import (
        build_address_steprepeat,
        build_artwork_gangup,
        compute_gangup_grid,
        merge_postcards,
        parse_usps_csv,
    )

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

        # ── 1. Merged PDF (individual pages per recipient) ─────────────────
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

        # Delete old output file before saving new one
        if job.output_file and job.output_file.name:
            try:
                job.output_file.delete(save=False)
            except Exception:
                pass
        job.output_file.save(
            f"{safe_name}_merged.pdf", ContentFile(output_buf.read()), save=False
        )

        # ── 2. Artwork gang-up ─────────────────────────────────────────────
        card_w = float(job.card_width) if job.card_width else None
        card_h = float(job.card_height) if job.card_height else None

        if card_w and card_h:
            cols, rows = compute_gangup_grid(card_w, card_h)
        else:
            cols, rows = 1, 1

        job.gangup_cols = cols
        job.gangup_rows = rows

        gangup_buf = io.BytesIO()
        build_artwork_gangup(
            io.BytesIO(artwork_bytes),
            cols, rows,
            864.0, 1296.0,  # 12 × 18 in
            gangup_buf,
        )
        gangup_buf.seek(0)

        if job.gangup_file and job.gangup_file.name:
            try:
                job.gangup_file.delete(save=False)
            except Exception:
                pass
        job.gangup_file.save(
            f"{safe_name}_gangup.pdf", ContentFile(gangup_buf.read()), save=False
        )

        # ── 3. Address step-and-repeat PDF ────────────────────────────────
        addr_x_pt = addr_x_in * 72.0 if addr_x_in is not None else None
        addr_y_pt = addr_y_in * 72.0 if addr_y_in is not None else None

        addr_buf = io.BytesIO()
        build_address_steprepeat(
            records,
            card_w or 432.0,
            card_h or 288.0,
            cols, rows,
            864.0, 1296.0,
            addr_x_pt,
            addr_y_pt,
            addr_buf,
        )
        addr_buf.seek(0)

        if job.address_pdf_file and job.address_pdf_file.name:
            try:
                job.address_pdf_file.delete(save=False)
            except Exception:
                pass
        job.address_pdf_file.save(
            f"{safe_name}_addresses.pdf", ContentFile(addr_buf.read()), save=False
        )

        job.status = MailMergeJob.Status.DONE
        job.save(update_fields=[
            "output_file", "gangup_file", "address_pdf_file",
            "gangup_cols", "gangup_rows", "status",
        ])
    except Exception as exc:
        logger.exception("Mail-merge failed for job %s", job_id)
        job.status = MailMergeJob.Status.ERROR
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message"])
