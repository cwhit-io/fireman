"""
Send PDFs to Fiery via LPD (lpr) or IPP (lp).
"""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def _build_lpr_command(
    preset, pdf_path: str, title: str = "", duplex_override: str | None = None
) -> list[str]:
    """Build the lpr command list for the given preset."""
    from django.conf import settings

    print_user = getattr(settings, "FIERY_PRINT_USER", "Ember")
    cmd = [
        "lpr",
        "-P",
        preset.printer_queue,
        "-#",
        str(preset.copies),
        "-U",
        print_user,
    ]

    if title:
        cmd += ["-T", title]

    # Prevent the printer from auto-scaling the PDF to fit its media
    cmd += ["-o", "fit-to-page=false"]

    # New-style Fiery PPD options (takes precedence)
    for key, value in (preset.fiery_options or {}).items():
        if value:
            cmd += ["-o", f"{key}={value}"]

    # Legacy field fallback for presets that pre-date fiery_options
    if not preset.fiery_options:
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

    # Per-job duplex override — applied after preset options so it takes effect
    if duplex_override:
        sides_map = {
            "duplex_long": "two-sided-long-edge",
            "duplex_short": "two-sided-short-edge",
            "simplex": "one-sided",
        }
        sides_value = sides_map.get(duplex_override, duplex_override)
        cmd += ["-o", f"sides={sides_value}"]

    # Free-text extra options always appended last
    for line in preset.extra_lpr_options.splitlines():
        line = line.strip()
        if line:
            cmd += ["-o", line]

    cmd.append(pdf_path)
    return cmd


def send_to_fiery_lpr(
    pdf_path: str,
    preset,
    dry_run: bool = False,
    title: str = "",
    duplex_override: str | None = None,
) -> subprocess.CompletedProcess | None:
    """
    Send *pdf_path* to Fiery via lpr using *preset*.

    If *dry_run* is True, log the command but do not execute it.
    Raises subprocess.CalledProcessError on failure.
    """
    if not shutil.which("lpr"):
        raise OSError("lpr is not available on this system.")

    cmd = _build_lpr_command(preset, pdf_path, title=title, duplex_override=duplex_override)
    logger.info("Sending to Fiery via lpr: %s", " ".join(cmd))

    if dry_run:
        return None

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result


def send_to_fiery_ipp(
    pdf_path: str, printer_uri: str, preset, dry_run: bool = False, title: str = ""
) -> subprocess.CompletedProcess | None:
    """
    Send *pdf_path* to Fiery via IPP using `lp`.
    """
    if not shutil.which("lp"):
        raise OSError("lp is not available on this system.")

    from django.conf import settings

    print_user = getattr(settings, "FIERY_PRINT_USER", "Ember")
    cmd = ["lp", "-d", printer_uri, "-n", str(preset.copies), "-U", print_user]
    if title:
        cmd += ["-t", title]

    # Fiery PPD options
    for key, value in (preset.fiery_options or {}).items():
        if value:
            cmd += ["-o", f"{key}={value}"]

    # Legacy fallback
    if not preset.fiery_options:
        if getattr(preset, "media_size", ""):
            cmd += ["-o", f"media={preset.media_size}"]
        if getattr(preset, "media_type", ""):
            cmd += ["-o", f"MediaType={preset.media_type}"]
        if getattr(preset, "duplex", "") and preset.duplex != "simplex":
            sides_map = {
                "duplex_long": "two-sided-long-edge",
                "duplex_short": "two-sided-short-edge",
            }
            cmd += ["-o", f"sides={sides_map.get(preset.duplex, 'one-sided')}"]
        if getattr(preset, "color_mode", "") == "grayscale":
            cmd += ["-o", "ColorModel=Gray"]

    # Free-text extra options always appended last
    for line in preset.extra_lpr_options.splitlines():
        line = line.strip()
        if line:
            cmd += ["-o", line]

    cmd.append(pdf_path)
    logger.info("Sending to Fiery via IPP: %s", " ".join(cmd))

    if dry_run:
        return None

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result


def test_printer_connection(preset) -> dict:
    """
    Check that the printer queue named in *preset* is reachable.

    Returns a dict with:
      ``ok``      – True if the queue responded, False otherwise
      ``message`` – Human-readable result string
    """
    queue = preset.printer_queue.strip()
    if not queue:
        return {"ok": False, "message": "No printer queue configured."}

    # Use lpstat to query the specific queue without sending any data.
    if shutil.which("lpstat"):
        try:
            result = subprocess.run(
                ["lpstat", "-p", queue],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                status_line = (
                    result.stdout.strip().splitlines()[0]
                    if result.stdout.strip()
                    else f"printer {queue} is idle."
                )
                return {"ok": True, "message": status_line}
            else:
                err = (result.stderr or result.stdout).strip()
                return {
                    "ok": False,
                    "message": err or f"Queue '{queue}' not found or unreachable.",
                }
        except subprocess.TimeoutExpired:
            return {"ok": False, "message": f"Timed out connecting to queue '{queue}'."}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    # Fall back to lp if lpstat is unavailable.
    if shutil.which("lp"):
        try:
            result = subprocess.run(
                ["lp", "-d", queue, "--", "/dev/null"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return {
                    "ok": True,
                    "message": f"Queue '{queue}' accepted a test request.",
                }
            else:
                err = (result.stderr or result.stdout).strip()
                return {
                    "ok": False,
                    "message": err or f"Queue '{queue}' rejected the test request.",
                }
        except subprocess.TimeoutExpired:
            return {"ok": False, "message": f"Timed out connecting to queue '{queue}'."}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    return {
        "ok": False,
        "message": "Neither lpstat nor lp is available on this system.",
    }
