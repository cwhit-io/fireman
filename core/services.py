"""Shared business-logic helpers used across multiple apps."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.jobs.models import PrintJob


def get_job_barcode_config(job: PrintJob) -> dict:
    """
    Returns the correct barcode configuration for a PrintJob.

    Checks ImpositionTemplate first, then falls back to job.cutter_program.

    Returns a dict with keys:
        barcode_value, barcode_x, barcode_y, barcode_width, barcode_height
    All positional values are float or None.
    """
    cp = None
    tmpl = job.imposition_template
    if tmpl and tmpl.cutter_program_id:
        cp = tmpl.cutter_program
    elif job.cutter_program_id:
        cp = job.cutter_program

    return {
        "barcode_value": cp.duplo_code if cp else None,
        "barcode_x": float(cp.barcode_x) if cp and cp.barcode_x is not None else None,
        "barcode_y": float(cp.barcode_y) if cp and cp.barcode_y is not None else None,
        "barcode_width": float(cp.barcode_width) if cp and cp.barcode_width is not None else None,
        "barcode_height": float(cp.barcode_height) if cp and cp.barcode_height is not None else None,
    }
