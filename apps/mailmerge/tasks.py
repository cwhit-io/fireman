import io
import logging

from celery import shared_task
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@shared_task
def process_mail_merge_task(job_id: str) -> None:
    """Run the mail-merge for a MailMergeJob asynchronously.

    Produces two output files by default (merged PDF is skipped to avoid
    generating a potentially very large file):

    1. ``gangup_file`` — artwork gang-up press sheet (N-up, for Fiery master).
    2. ``address_pdf_file`` — address step-and-repeat PDF (one sheet per N records).

    Call :func:`generate_merged_pdf_task` to generate the full merged PDF on demand.
    """
    from .models import MailMergeJob
    from .services import (
        build_address_steprepeat,
        build_artwork_gangup,
        compute_gangup_grid,
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
        # Load site-wide address block config
        from .models import AddressBlockConfig

        addr_config = AddressBlockConfig.get_solo()
        cfg_font_name = addr_config.font_name or None
        cfg_font_size = float(addr_config.font_size) if addr_config.font_size else None
        cfg_line_height = (
            float(addr_config.line_height) if addr_config.line_height else None
        )
        cfg_fields = addr_config.csv_fields or None
        cfg_barcode_font_size = (
            float(addr_config.barcode_font_size)
            if addr_config.barcode_font_size
            else None
        )
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

        safe_name = job.name or f"mailmerge_{job.pk}"

        # ── 1. Artwork gang-up ─────────────────────────────────────────────
        # Use impose_template sheet dimensions if available; otherwise 12×18"
        card_w = float(job.card_width) if job.card_width else None
        card_h = float(job.card_height) if job.card_height else None

        if job.impose_template:
            sheet_w = float(job.impose_template.sheet_width)
            sheet_h = float(job.impose_template.sheet_height)
            cols = job.impose_template.columns
            rows = job.impose_template.rows
        else:
            sheet_w = 864.0  # 12 in
            sheet_h = 1296.0  # 18 in
            if card_w and card_h:
                cols, rows = compute_gangup_grid(card_w, card_h)
            else:
                cols, rows = 1, 1

        job.gangup_cols = cols
        job.gangup_rows = rows

        gangup_buf = io.BytesIO()
        build_artwork_gangup(
            io.BytesIO(artwork_bytes),
            cols,
            rows,
            sheet_w,
            sheet_h,
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

        # ── 2. Address step-and-repeat PDF ────────────────────────────────
        addr_x_pt = addr_x_in * 72.0 if addr_x_in is not None else None
        addr_y_pt = addr_y_in * 72.0 if addr_y_in is not None else None

        addr_buf = io.BytesIO()
        build_address_steprepeat(
            records,
            card_w or 432.0,
            card_h or 288.0,
            cols,
            rows,
            sheet_w,
            sheet_h,
            addr_x_pt,
            addr_y_pt,
            addr_buf,
            font_name=cfg_font_name,
            font_size=cfg_font_size,
            line_height=cfg_line_height,
            fields=cfg_fields,
            barcode_font_size=cfg_barcode_font_size,
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
        job.save(
            update_fields=[
                "gangup_file",
                "address_pdf_file",
                "gangup_cols",
                "gangup_rows",
                "status",
            ]
        )
    except Exception as exc:
        logger.exception("Mail-merge failed for job %s", job_id)
        job.status = MailMergeJob.Status.ERROR
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message"])


@shared_task
def generate_merged_pdf_task(job_id: str) -> None:
    """Generate the full merged PDF for a completed MailMergeJob on demand.

    This produces ``output_file`` — one page (or two pages for duplex artwork)
    per recipient.  It is not generated automatically because the file can be
    very large for high-volume jobs.
    """
    from .models import MailMergeJob
    from .services import merge_postcards, parse_usps_csv

    try:
        job = MailMergeJob.objects.get(pk=job_id)
    except MailMergeJob.DoesNotExist:
        logger.error("MailMergeJob %s not found", job_id)
        return

    try:
        with job.csv_file.open("rb") as csv_fh:
            records = parse_usps_csv(csv_fh)

        if not records:
            raise ValueError("CSV file contains no address records.")

        with job.artwork_file.open("rb") as art_fh:
            artwork_bytes = art_fh.read()

        addr_x_in = float(job.addr_x_in) if job.addr_x_in is not None else None
        addr_y_in = float(job.addr_y_in) if job.addr_y_in is not None else None

        # Load site-wide address block config
        from .models import AddressBlockConfig

        addr_config = AddressBlockConfig.get_solo()
        cfg_font_name = addr_config.font_name or None
        cfg_font_size = float(addr_config.font_size) if addr_config.font_size else None
        cfg_line_height = (
            float(addr_config.line_height) if addr_config.line_height else None
        )
        cfg_fields = addr_config.csv_fields or None
        cfg_barcode_font_size = (
            float(addr_config.barcode_font_size)
            if addr_config.barcode_font_size
            else None
        )

        output_buf = io.BytesIO()
        merge_postcards(
            io.BytesIO(artwork_bytes),
            records,
            output_buf,
            merge_page=job.merge_page or 1,
            addr_x_in=addr_x_in,
            addr_y_in=addr_y_in,
            font_name=cfg_font_name,
            font_size=cfg_font_size,
            line_height=cfg_line_height,
            fields=cfg_fields,
            barcode_font_size=cfg_barcode_font_size,
        )
        output_buf.seek(0)
        safe_name = job.name or f"mailmerge_{job.pk}"

        if job.output_file and job.output_file.name:
            try:
                job.output_file.delete(save=False)
            except Exception:
                pass
        job.output_file.save(
            f"{safe_name}_merged.pdf", ContentFile(output_buf.read()), save=False
        )
        job.save(update_fields=["output_file"])
    except Exception:
        logger.exception("Merged PDF generation failed for job %s", job_id)
