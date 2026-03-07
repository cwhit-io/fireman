"""
Send PDFs to Fiery via LPD (lpr) or IPP (lp).
"""
from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def _build_lpr_command(preset, pdf_path: str) -> list[str]:
    """Build the lpr command list for the given preset."""
    cmd = ["lpr", "-P", preset.printer_queue, "-#", str(preset.copies)]

    if preset.media_size:
        cmd += ["-o", f"media={preset.media_size}"]
    if preset.media_type:
        cmd += ["-o", f"MediaType={preset.media_type}"]
    if preset.duplex and preset.duplex != "simplex":
        sides_map = {
            "duplex_long": "two-sided-long-edge",
            "duplex_short": "two-sided-short-edge",
        }
        cmd += ["-o", f"sides={sides_map.get(preset.duplex, 'one-sided')}"]
    if preset.color_mode == "grayscale":
        cmd += ["-o", "ColorModel=Gray"]
    if preset.tray:
        cmd += ["-o", f"InputSlot={preset.tray}"]

    for line in preset.extra_lpr_options.splitlines():
        line = line.strip()
        if line:
            cmd += ["-o", line]

    cmd.append(pdf_path)
    return cmd


def send_to_fiery_lpr(pdf_path: str, preset, dry_run: bool = False) -> subprocess.CompletedProcess | None:
    """
    Send *pdf_path* to Fiery via lpr using *preset*.

    If *dry_run* is True, log the command but do not execute it.
    Raises subprocess.CalledProcessError on failure.
    """
    if not shutil.which("lpr"):
        raise OSError("lpr is not available on this system.")

    cmd = _build_lpr_command(preset, pdf_path)
    logger.info("Sending to Fiery via lpr: %s", " ".join(cmd))

    if dry_run:
        return None

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result


def send_to_fiery_ipp(pdf_path: str, printer_uri: str, preset, dry_run: bool = False) -> subprocess.CompletedProcess | None:
    """
    Send *pdf_path* to Fiery via IPP using `lp`.
    """
    if not shutil.which("lp"):
        raise OSError("lp is not available on this system.")

    cmd = ["lp", "-d", printer_uri, "-n", str(preset.copies), pdf_path]
    logger.info("Sending to Fiery via IPP: %s", " ".join(cmd))

    if dry_run:
        return None

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result
