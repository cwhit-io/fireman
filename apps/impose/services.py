"""
Imposition services — wrap PyPDF to place input pages onto press sheets.
"""
from __future__ import annotations

import io
import logging
from typing import IO

logger = logging.getLogger(__name__)


def _pts(inches: float) -> float:
    return inches * 72.0


def impose_nup(
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
    columns: int,
    rows: int,
    sheet_width: float,
    sheet_height: float,
    bleed: float = 0.0,
    margin_top: float = 0.0,
    margin_right: float = 0.0,
    margin_bottom: float = 0.0,
    margin_left: float = 0.0,
) -> None:
    """
    Tile *columns × rows* source pages onto new press sheets and write to *output_pdf*.

    All dimensions are in PDF points (72 pts = 1 inch).
    """
    from pypdf import PageObject, PdfReader, PdfWriter, Transformation

    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    per_sheet = columns * rows
    pages_up = list(reader.pages)
    if not pages_up:
        return

    printable_w = sheet_width - margin_left - margin_right
    printable_h = sheet_height - margin_top - margin_bottom
    cell_w = printable_w / columns
    cell_h = printable_h / rows

    for sheet_start in range(0, len(pages_up), per_sheet):
        sheet = PageObject.create_blank_page(width=sheet_width, height=sheet_height)
        for idx in range(per_sheet):
            page_idx = sheet_start + idx
            if page_idx >= len(pages_up):
                break
            src = pages_up[page_idx]

            col = idx % columns
            row = idx // columns

            src_w = float(src.mediabox.width)
            src_h = float(src.mediabox.height)

            scale_x = (cell_w - 2 * bleed) / src_w if src_w else 1.0
            scale_y = (cell_h - 2 * bleed) / src_h if src_h else 1.0
            scale = min(scale_x, scale_y)

            tx = margin_left + col * cell_w + bleed + (cell_w - 2 * bleed - src_w * scale) / 2
            ty = sheet_height - margin_top - (row + 1) * cell_h + bleed + (cell_h - 2 * bleed - src_h * scale) / 2

            transform = Transformation().scale(scale).translate(tx, ty)
            sheet.merge_transformed_page(src, transform)

        writer.add_page(sheet)

    writer.write(output_pdf)


def impose_step_repeat(
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
    columns: int,
    rows: int,
    sheet_width: float,
    sheet_height: float,
    bleed: float = 0.0,
) -> None:
    """Repeat a single source page *columns × rows* times (step-and-repeat)."""
    from pypdf import PdfReader

    reader = PdfReader(input_pdf)
    if not reader.pages:
        return

    from pypdf import PdfWriter

    buf = io.BytesIO()
    w = PdfWriter()
    w.add_page(reader.pages[0])
    w.write(buf)
    buf.seek(0)

    impose_nup(
        buf,
        output_pdf,
        columns=columns,
        rows=rows,
        sheet_width=sheet_width,
        sheet_height=sheet_height,
        bleed=bleed,
    )


def impose_business_card_21up(
    input_pdf: IO[bytes],
    output_pdf: IO[bytes],
) -> None:
    """
    Standard 21-up business card imposition on a 12.5 × 19 in sheet.
    Business cards are 3.5 × 2 in; 3 columns × 7 rows.
    """
    impose_nup(
        input_pdf,
        output_pdf,
        columns=3,
        rows=7,
        sheet_width=_pts(12.5),
        sheet_height=_pts(19.0),
        bleed=_pts(0.125),
        margin_top=_pts(0.25),
        margin_right=_pts(0.25),
        margin_bottom=_pts(0.25),
        margin_left=_pts(0.25),
    )


def impose_from_template(template, input_pdf: IO[bytes], output_pdf: IO[bytes]) -> None:
    """Dispatch imposition to the right function based on *template.layout_type*."""
    from apps.impose.models import ImpositionTemplate

    lt = template.layout_type
    sheet_w = float(template.sheet_width)
    sheet_h = float(template.sheet_height)
    bleed = float(template.bleed)

    if lt == ImpositionTemplate.LayoutType.STEP_REPEAT:
        impose_step_repeat(
            input_pdf, output_pdf,
            columns=template.columns,
            rows=template.rows,
            sheet_width=sheet_w,
            sheet_height=sheet_h,
            bleed=bleed,
        )
    elif lt == ImpositionTemplate.LayoutType.BUSINESS_CARD:
        impose_business_card_21up(input_pdf, output_pdf)
    else:
        impose_nup(
            input_pdf, output_pdf,
            columns=template.columns,
            rows=template.rows,
            sheet_width=sheet_w,
            sheet_height=sheet_h,
            bleed=bleed,
            margin_top=float(template.margin_top),
            margin_right=float(template.margin_right),
            margin_bottom=float(template.margin_bottom),
            margin_left=float(template.margin_left),
        )
