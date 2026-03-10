"""
Preflight validation for print-ready PDFs.

All rules are non-blocking — each produces a status + corrective action
+ user-friendly Ember message.  Thresholds are loaded from Django settings
(which in turn read from .env with sane defaults).

Evaluation order (per spec):
  1. Colorspace  → Rule 8
  2. DPI         → Rule 9
  3. Safe zone   → Rule 10
  4. Size vs trim
       ├── Match ±TOLERANCE  → bleed check (Rules 1-4, 7)
       ├── Wrong size, AR ≤2% → scale to trim → bleed check (Rule 5)
       └── Wrong size, AR >2% → scale to fill (Rule 6)
  5. Return PreflightResult
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Literal

from django.conf import settings

logger = logging.getLogger(__name__)


# ─────────────── Ember messages ─────────────────────────────────────────────

PREFLIGHT_MESSAGES: dict[str, str] = {
    "R1": (
        "🐾 Ember sniffed around the edges and couldn't find any bleed! She nudged "
        "the artwork out a little to cover the trim zone. Double-check that nothing "
        "important got clipped at the edges."
    ),
    "R2": (
        "✅ Ember gave this one a big sniff of approval — bleed looks great and "
        "everything is right where it should be. Good to go!"
    ),
    "R3": (
        "✂️ Canva left some crop marks on this one — Ember chewed those right off. "
        "Your bleed is intact and the file is ready to print!"
    ),
    "R4": (
        "🐾 Ember is sitting and staring at this file with her head tilted. It's "
        "oversized in a way she doesn't recognize. A human should take a look "
        "before this one goes to print."
    ),
    "R5": (
        "📐 The file wasn't quite the right size, but the proportions looked good — "
        "Ember scaled it to fit and is re-checking the bleed now."
    ),
    "R6": (
        "🚨 Ember is barking. Loudly. The file proportions don't match the target "
        "size — it's been scaled to fill but the artwork may be stretched or "
        "squished. Please verify before sending to print."
    ),
    "R7": (
        "🐾 Ember found a bleed, but it's a little thin — she stretched it out to "
        'the full 0.125". Keep an eye on the edges just in case.'
    ),
    "R8": (
        "🎨 Woof! This file is in RGB color mode, which isn't ideal for printing. "
        "Colors may shift when converted to CMYK. An operator should review "
        "before this goes to press."
    ),
    "R9_MARGINAL": (
        "🔍 Ember squinted at some of the images in this file — resolution is a "
        "little low (under 300 DPI). It might print okay, but it might not be "
        "as crisp as you'd like."
    ),
    "R9_CRITICAL": (
        "🐾 Ember can't even make out what she's looking at — some images in this "
        "file are under 150 DPI and will likely look pixelated when printed. "
        "Please replace with higher resolution artwork."
    ),
    "R10": (
        "📏 Heads up — Ember spotted some text or artwork that's cutting it close "
        "to the trim edge. Anything important should be at least 0.125\" inside "
        "the trim line or it might get cut off."
    ),
}


# ─────────────── Result dataclass ───────────────────────────────────────────

@dataclass
class PreflightResult:
    status: Literal["ok", "warn", "error"] = "ok"
    rules_triggered: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    modified: bool = False
    original_size: tuple[float, float] = (0.0, 0.0)
    output_size: tuple[float, float] = (0.0, 0.0)
    notes: list[str] = field(default_factory=list)

    _STATUS_RANK: dict[str, int] = field(
        default_factory=lambda: {"ok": 0, "info": 0, "warn": 1, "error": 2},
        repr=False,
        compare=False,
    )

    def _elevate(self, new_status: str) -> None:
        rank = {"ok": 0, "info": 0, "warn": 1, "error": 2}
        if rank.get(new_status, 0) > rank.get(self.status, 0):
            self.status = new_status  # type: ignore[assignment]

    def add(
        self,
        rule_id: str,
        *,
        status: str = "warn",
        note: str = "",
    ) -> None:
        """Record a triggered rule using the canonical Ember message."""
        if rule_id not in self.rules_triggered:
            self.rules_triggered.append(rule_id)
            msg = PREFLIGHT_MESSAGES.get(rule_id, f"Rule {rule_id} triggered.")
            self.messages.append(msg)
        if note:
            self.notes.append(note)
        self._elevate(status)


# ─────────────── Config helpers ─────────────────────────────────────────────

def _cfg_float(name: str, default: float) -> float:
    return float(getattr(settings, name, default))


def _cfg_int(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


def _cfg_bool(name: str, default: bool) -> bool:
    return bool(getattr(settings, name, default))


# ─────────────── Helpers ────────────────────────────────────────────────────

def _ar_delta_pct(w1: float, h1: float, w2: float, h2: float) -> float:
    """Return the aspect-ratio difference as a percentage."""
    if h1 == 0 or h2 == 0:
        return 100.0
    ar1 = w1 / h1
    ar2 = w2 / h2
    return abs(ar1 - ar2) / max(ar1, ar2) * 100.0


def _detect_rgb_colorspace(page) -> bool:
    """Return True if any resource on the page appears to use an RGB colorspace."""
    try:
        resources = page.get("/Resources")
        if resources is None:
            return False
        cs_dict = resources.get("/ColorSpace", {})
        for _k, cs in (cs_dict or {}).items():
            if hasattr(cs, "__iter__"):
                cs_list = list(cs)
                if cs_list and str(cs_list[0]) in ("/DeviceRGB", "/sRGB"):
                    return True
        # Check inline image XObjects
        xobj = resources.get("/XObject", {})
        for _k, xobj_ref in (xobj or {}).items():
            try:
                xobj_obj = xobj_ref.get_object() if hasattr(xobj_ref, "get_object") else xobj_ref
                subtype = xobj_obj.get("/Subtype", "")
                if str(subtype) == "/Image":
                    cs = xobj_obj.get("/ColorSpace", "")
                    if str(cs) in ("/DeviceRGB", "/sRGB"):
                        return True
                    if hasattr(cs, "__iter__"):
                        cs_parts = list(cs)
                        if cs_parts and str(cs_parts[0]) in ("/DeviceRGB", "/sRGB"):
                            return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _check_image_dpi(page, trim_w_pt: float, trim_h_pt: float) -> tuple[int | None, int | None]:
    """
    Return (min_dpi, critical_dpi_below_minimum) for raster images on the page.

    Returns (None, None) if no raster images are found (pure vector).
    """
    min_dpi_found: int | None = None
    critical_dpi: int | None = None

    try:
        resources = page.get("/Resources")
        if resources is None:
            return None, None
        xobj = resources.get("/XObject", {})
        if not xobj:
            return None, None

        for _k, xobj_ref in xobj.items():
            try:
                xobj_obj = xobj_ref.get_object() if hasattr(xobj_ref, "get_object") else xobj_ref
                subtype = xobj_obj.get("/Subtype", "")
                if str(subtype) != "/Image":
                    continue
                pix_w = int(xobj_obj.get("/Width", 0))
                pix_h = int(xobj_obj.get("/Height", 0))
                if pix_w <= 0 or pix_h <= 0:
                    continue
                # Use trim dimensions as rendered size estimate
                rendered_w = trim_w_pt / 72.0
                rendered_h = trim_h_pt / 72.0
                if rendered_w <= 0 or rendered_h <= 0:
                    continue
                dpi_x = int(pix_w / rendered_w)
                dpi_y = int(pix_h / rendered_h)
                dpi = min(dpi_x, dpi_y)
                if min_dpi_found is None or dpi < min_dpi_found:
                    min_dpi_found = dpi
                dpi_minimum = _cfg_int("DPI_MINIMUM", 150)
                if dpi < dpi_minimum:
                    if critical_dpi is None or dpi < critical_dpi:
                        critical_dpi = dpi
            except Exception:
                continue
    except Exception:
        pass

    return min_dpi_found, critical_dpi


def _check_safe_zone(page, trim_w_pt: float, trim_h_pt: float, safe_zone_pt: float) -> bool:
    """
    Best-effort: check if any text object has its origin within safe_zone_pt
    of the trim edge.  Returns True if a violation is detected.
    """
    try:
        # Offset if the trim box is inset within the media box
        trimbox = page.get("/TrimBox")
        if trimbox:
            try:
                tb = [float(v) for v in trimbox]
                trim_left = tb[0]
                trim_bottom = tb[1]
                trim_right = tb[2]
                trim_top = tb[3]
            except Exception:
                trim_left = 0.0
                trim_bottom = 0.0
                trim_right = trim_w_pt
                trim_top = trim_h_pt
        else:
            trim_left = 0.0
            trim_bottom = 0.0
            trim_right = trim_w_pt
            trim_top = trim_h_pt

        # Parse content stream for text positions via Tj/TJ operators
        try:
            extracted = page.extract_text()
            if not extracted:
                return False
        except Exception:
            return False

        # Use visitor-based extraction to get text positions
        violations = [False]

        def visitor_text(text, cm, tm, fontDict, fontSize):
            if not text or not text.strip():
                return
            if tm is None:
                return
            # tm is a 6-element list: [a, b, c, d, e, f] where e=x, f=y
            try:
                x = float(tm[4])
                y = float(tm[5])
                if (
                    x < trim_left + safe_zone_pt
                    or x > trim_right - safe_zone_pt
                    or y < trim_bottom + safe_zone_pt
                    or y > trim_top - safe_zone_pt
                ):
                    violations[0] = True
            except Exception:
                pass

        try:
            page.extract_text(visitor_text=visitor_text)
        except Exception:
            pass

        return violations[0]
    except Exception:
        return False


# ─────────────── Main entry point ───────────────────────────────────────────

def run_preflight(
    pdf_bytes: bytes,
    trim_w_pt: float,
    trim_h_pt: float,
) -> PreflightResult:
    """
    Run all preflight rules against *pdf_bytes* and a target trim size.

    Parameters
    ----------
    pdf_bytes   Raw bytes of the (already validated/repaired) PDF.
    trim_w_pt   Finished trim width in points.
    trim_h_pt   Finished trim height in points.

    Returns
    -------
    PreflightResult
    """
    result = PreflightResult()

    if not pdf_bytes:
        result.notes.append("No PDF bytes provided — preflight skipped.")
        return result

    if trim_w_pt <= 0 or trim_h_pt <= 0:
        result.notes.append("No trim dimensions available — preflight skipped.")
        return result

    bleed_pt = _cfg_float("BLEED_PT", 9.0)
    canva_margin_pt = _cfg_float("CANVA_MARGIN_PT", 17.0)
    canva_wiggle_pt = _cfg_float("CANVA_WIGGLE_PT", 5.0)
    size_tol_pt = _cfg_float("SIZE_TOLERANCE_PT", 1.0)
    ar_tol_pct = _cfg_float("AR_TOLERANCE_PCT", 2.0)
    dpi_minimum = _cfg_int("DPI_MINIMUM", 150)
    dpi_warn = _cfg_int("DPI_WARN", 300)
    safe_zone_pt = _cfg_float("SAFE_ZONE_PT", 9.0)
    allow_rgb = _cfg_bool("ALLOW_RGB", False)

    try:
        from pypdf import PdfReader
    except ImportError:
        result.notes.append("pypdf not installed — preflight skipped.")
        return result

    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
    except Exception as exc:
        result.notes.append(f"Could not open PDF for preflight: {exc}")
        return result

    if not reader.pages:
        result.notes.append("PDF has no pages — preflight skipped.")
        return result

    page = reader.pages[0]
    mb = page.mediabox
    file_w = float(mb.width)
    file_h = float(mb.height)

    result.original_size = (file_w, file_h)
    result.output_size = (file_w, file_h)

    # ── 1. Colorspace (Rule 8) ────────────────────────────────────────────
    if not allow_rgb:
        if _detect_rgb_colorspace(page):
            result.add("R8", status="warn", note="RGB colorspace detected on page 1.")

    # ── 2. DPI (Rule 9) ──────────────────────────────────────────────────
    min_dpi, critical_dpi = _check_image_dpi(page, trim_w_pt, trim_h_pt)
    if min_dpi is not None:
        if critical_dpi is not None:
            result.add(
                "R9_CRITICAL",
                status="warn",
                note=f"Image DPI as low as {critical_dpi} (below {dpi_minimum}).",
            )
        elif min_dpi < dpi_warn:
            result.add(
                "R9_MARGINAL",
                status="warn",
                note=f"Lowest image DPI: {min_dpi} (below {dpi_warn}).",
            )

    # ── 3. Safe zone (Rule 10) ────────────────────────────────────────────
    if _check_safe_zone(page, trim_w_pt, trim_h_pt, safe_zone_pt):
        result.add(
            "R10",
            status="warn",
            note=f"Text detected within {safe_zone_pt}pt of trim edge.",
        )

    # ── 4. Size vs trim ──────────────────────────────────────────────────
    excess_w = file_w - trim_w_pt
    excess_h = file_h - trim_h_pt

    # "Product size match": file dimensions are consistent with trim + uniform bleed.
    # Criteria: neither dimension is smaller than trim (±tol), and any overage
    # is approximately equal on both axes (i.e. uniform bleed was added).
    not_too_small = excess_w >= -size_tol_pt and excess_h >= -size_tol_pt
    bleed_uniformity = abs(excess_w / 2.0 - excess_h / 2.0) <= size_tol_pt * 4
    in_expected_range = not_too_small and bleed_uniformity

    if not in_expected_range:
        ar_delta = _ar_delta_pct(file_w, file_h, trim_w_pt, trim_h_pt)
        if ar_delta <= ar_tol_pct:
            # Rule 5: wrong size, AR matches → scale to trim, re-eval bleed
            result.add("R5", status="warn", note=f"Scaled to trim ({trim_w_pt:.1f}×{trim_h_pt:.1f}pt). AR delta={ar_delta:.2f}%.")
            result.modified = True
            # Pretend file is now at trim size for bleed evaluation
            file_w, file_h = trim_w_pt, trim_h_pt
            excess_w = excess_h = 0.0
        else:
            # Rule 6: wrong size, AR mismatch
            result.add(
                "R6",
                status="warn",
                note=f"AR mismatch {ar_delta:.2f}% > {ar_tol_pct}%. Scaled to fill.",
            )
            result.modified = True
            result.output_size = (trim_w_pt, trim_h_pt)
            return result  # no further bleed checks

    # ── 5. Bleed checks (Rules 1-4, 7) when size is in expected range ───
    # Per-side overage: average of W and H per-side values
    overage_per_side = (excess_w + excess_h) / 4.0

    # Rule 7: BleedBox exists but delta < BLEED_PT - 2pt
    bleed_box = page.get("/BleedBox")
    trim_box = page.get("/TrimBox")
    if bleed_box and trim_box:
        try:
            bb = [float(v) for v in bleed_box]
            tb = [float(v) for v in trim_box]
            # Delta on each side
            left_delta = tb[0] - bb[0]
            bottom_delta = tb[1] - bb[1]
            right_delta = bb[2] - tb[2]
            top_delta = bb[3] - tb[3]
            min_bleed_declared = min(left_delta, bottom_delta, right_delta, top_delta)
            if 0 < min_bleed_declared < bleed_pt - 2:
                result.add(
                    "R7",
                    status="warn",
                    note=f"BleedBox delta {min_bleed_declared:.1f}pt < required {bleed_pt}pt.",
                )
                result.modified = True
        except Exception:
            pass
    else:
        # Evaluate overage rules
        if abs(overage_per_side) <= size_tol_pt:
            # Rule 1: Exact trim, no bleed
            result.add(
                "R1",
                status="warn",
                note=f"No bleed: overage={overage_per_side:.1f}pt. Scaling content up.",
            )
            result.modified = True
        elif bleed_pt - 2 <= overage_per_side <= bleed_pt + 2:
            # Rule 2: Exact trim + clean bleed
            result.add("R2", status="ok", note=f"Bleed overage={overage_per_side:.1f}pt. Accepted.")
        elif (canva_margin_pt - canva_wiggle_pt) <= overage_per_side <= (canva_margin_pt + canva_wiggle_pt):
            # Rule 3: Canva-style export
            result.add("R3", status="ok", note=f"Canva-style overage={overage_per_side:.1f}pt. Cropped.")
            result.modified = True
        elif overage_per_side > canva_margin_pt + canva_wiggle_pt:
            # Rule 4: Oversized, unrecognized
            result.add(
                "R4",
                status="warn",
                note=f"Oversized: overage={overage_per_side:.1f}pt > {canva_margin_pt + canva_wiggle_pt}pt.",
            )
        else:
            # Between rule 2 and rule 3 territory — treat as valid bleed
            result.add("R2", status="ok", note=f"Bleed overage={overage_per_side:.1f}pt.")

    result.output_size = (file_w, file_h)
    return result
