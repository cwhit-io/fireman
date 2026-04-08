"""
Send PDFs to Fiery via LPD (lpr) or IPP (lp).
"""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Map common press-sheet dimensions (PDF points, portrait) to PPD PageSize names.
# Tolerance of ±3 pt (~0.04") handles rounding differences between PDF writers.
_SHEET_SIZE_PPD: list[tuple[int, int, str]] = [
    (612, 792, "Letter"),  # 8.5 × 11"
    (792, 1224, "Tabloid"),  # 11 × 17"
    (864, 1296, "TabloidExtra"),  # 12 × 18"
    (936, 1368, "13x19"),  # 13 × 19"
    (907, 1382, "13x19.2R"),  # 13 × 19.2"
    (907, 1339, "12.6x18.5"),  # 12.6 × 18.5"
    (907, 1382, "12.6x19.2"),  # 12.6 × 19.2"
    (936, 1296, "13x18"),  # 13 × 18"
    (612, 1008, "Legal"),  # 8.5 × 14"
    (396, 612, "Statement"),  # 5.5 × 8.5"
    (595, 842, "A4"),  # A4
    (420, 595, "A5"),  # A5
]
_PPD_SIZE_TOL = 3  # points


def _page_size_ppd_name(pdf_path: str) -> str | None:
    """Return a CUPS/Fiery PPD PageSize string for the first page of *pdf_path*.

    Tries well-known named sizes first; falls back to ``Custom.WxH`` (points).
    Returns ``None`` if the PDF cannot be read.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(pdf_path)
        if not reader.pages:
            return None
        mb = reader.pages[0].mediabox
        w = round(float(mb.width))
        h = round(float(mb.height))
    except Exception:
        logger.warning("Could not read page dimensions from %r", pdf_path)
        return None

    for sw, sh, name in _SHEET_SIZE_PPD:
        if (abs(w - sw) <= _PPD_SIZE_TOL and abs(h - sh) <= _PPD_SIZE_TOL) or (
            abs(w - sh) <= _PPD_SIZE_TOL and abs(h - sw) <= _PPD_SIZE_TOL
        ):
            return name

    # Non-standard size — use CUPS custom page size syntax (points).
    return f"Custom.{w}x{h}"


def _page_size_already_set(fiery_options: dict, extra_lpr_options: str) -> bool:
    """Return True if PageSize is already covered by the preset's options."""
    if "PageSize" in (fiery_options or {}):
        return True
    for line in extra_lpr_options.splitlines():
        if line.strip().startswith("PageSize="):
            return True
    return False


def _build_lpr_command(
    preset,
    pdf_path: str,
    title: str = "",
    duplex_override: str | None = None,
    print_user: str | None = None,
) -> list[str]:
    """Build the lpr command list for the given preset."""
    from django.conf import settings

    if print_user is None:
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

    # Prevent the printer from auto-scaling the PDF to fit its media.
    # fit-to-page=false is the generic CUPS attribute; EFScaleToFit=OFF is the
    # Fiery-native PPD key.  Both are sent so either path is covered.
    cmd += ["-o", "fit-to-page=false"]
    cmd += ["-o", "EFScaleToFit=OFF"]

    # Tell CUPS the correct PageSize so it does not default to Letter.
    # Without this, the PPD default (usually Letter/8.5×11) overrides the
    # actual PDF dimensions before the job even reaches Fiery.
    if not _page_size_already_set(preset.fiery_options, preset.extra_lpr_options):
        ps = _page_size_ppd_name(pdf_path)
        if ps:
            cmd += ["-o", f"PageSize={ps}"]

    # New-style Fiery PPD options (takes precedence)
    for key, value in (preset.fiery_options or {}).items():
        if value:
            cmd += ["-o", f"{key}={value}"]

    # Per-job duplex override — applied after preset options so it takes effect.
    # Fiery PPD presets use EFDuplex; legacy/standard CUPS presets use sides=.
    if duplex_override:
        if preset.fiery_options:
            ef_duplex_map = {
                "duplex_long": "TopTop",
                "duplex_short": "TopBottom",
                "simplex": "False",
            }
            ef_value = ef_duplex_map.get(duplex_override, "False")
            cmd += ["-o", f"EFDuplex={ef_value}"]
        else:
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
    print_user: str | None = None,
) -> subprocess.CompletedProcess | None:
    """
    Send *pdf_path* to Fiery via lpr using *preset*.

    If *dry_run* is True, log the command but do not execute it.
    Raises subprocess.CalledProcessError on failure.
    """
    if not shutil.which("lpr"):
        raise OSError("lpr is not available on this system.")

    cmd = _build_lpr_command(
        preset,
        pdf_path,
        title=title,
        duplex_override=duplex_override,
        print_user=print_user,
    )
    logger.info("Sending to Fiery via lpr: %s", " ".join(cmd))

    if dry_run:
        return None

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result


def send_to_fiery_ipp(
    pdf_path: str, printer_uri: str, preset, dry_run: bool = False, title: str = "",
    print_user: str | None = None,
) -> subprocess.CompletedProcess | None:
    """
    Send *pdf_path* to Fiery via IPP using `lp`.
    """
    if not shutil.which("lp"):
        raise OSError("lp is not available on this system.")

    from django.conf import settings

    if print_user is None:
        print_user = getattr(settings, "FIERY_PRINT_USER", "Ember")
    cmd = ["lp", "-d", printer_uri, "-n", str(preset.copies), "-U", print_user]
    if title:
        cmd += ["-t", title]

    # Prevent the printer from auto-scaling the PDF to fit its media.
    # fit-to-page=false is the generic CUPS attribute; EFScaleToFit=OFF is the
    # Fiery-native PPD key.  Both are sent so either path is covered.
    cmd += ["-o", "fit-to-page=false"]
    cmd += ["-o", "EFScaleToFit=OFF"]

    # Tell CUPS the correct PageSize so it does not default to Letter.
    if not _page_size_already_set(preset.fiery_options, preset.extra_lpr_options):
        ps = _page_size_ppd_name(pdf_path)
        if ps:
            cmd += ["-o", f"PageSize={ps}"]

    # Fiery PPD options
    for key, value in (preset.fiery_options or {}).items():
        if value:
            cmd += ["-o", f"{key}={value}"]

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
