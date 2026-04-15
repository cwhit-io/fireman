import io
import os
import re

import cairosvg
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import BrandAsset, BrandAssetCategory, BrandColor

# Resolution multiplier used for PNG export (2× = ~192 dpi at 96 dpi base → 300+ dpi effective)
PNG_SCALE = 3.125  # 96 × 3.125 = 300 dpi

_SVG_STYLE_TPL = (
    '<style type="text/css">'
    "* {{ fill: {c} !important; stroke: {c} !important; }}"
    ' *[fill="none"] {{ fill: none !important; }}'
    ' *[stroke="none"] {{ stroke: none !important; }}'
    "</style>"
)


def _apply_svg_variant(svg_bytes: bytes, variant: str) -> bytes:
    """Return SVG bytes recoloured to all-black or all-white.

    Injects a CSS <style> block immediately after the opening <svg> tag so that
    all fill/stroke values are overridden while transparent elements (fill="none")
    are left untouched.
    """
    if variant not in ("black", "white"):
        return svg_bytes

    color = "#000000" if variant == "black" else "#ffffff"
    style_block = _SVG_STYLE_TPL.format(c=color)
    svg_text = svg_bytes.decode("utf-8", errors="replace")
    svg_text, n = re.subn(
        r"(<svg\b[^>]*>)", r"\g<1>" + style_block, svg_text, count=1, flags=re.DOTALL
    )
    if not n:
        # malformed SVG with no <svg> tag — prepend style block as fallback
        svg_text = style_block + svg_text
    return svg_text.encode("utf-8")


@login_required
@require_GET
def brand_assets_page(request):
    categories = BrandAssetCategory.objects.prefetch_related("assets").order_by("order", "name")
    # Uncategorised assets
    uncategorised = BrandAsset.objects.filter(category__isnull=True).order_by("order", "name")
    colors = BrandColor.objects.order_by("order", "name")

    return render(request, "brand_assets/index.html", {
        "categories": categories,
        "uncategorised": uncategorised,
        "colors": colors,
    })


@login_required
@require_GET
def download_asset(request, pk):
    asset = get_object_or_404(BrandAsset, pk=pk)
    fmt = request.GET.get("format", "svg").lower()
    variant = request.GET.get("variant", "color").lower()

    if fmt not in ("svg", "pdf", "png"):
        raise Http404("Unsupported format.")
    if variant not in ("color", "black", "white"):
        variant = "color"

    try:
        svg_bytes = asset.svg_file.read()
    except Exception:
        raise Http404("Asset file not found.")

    svg_bytes = _apply_svg_variant(svg_bytes, variant)

    stem = os.path.splitext(os.path.basename(asset.svg_file.name))[0]
    variant_suffix = f"_{variant}" if variant != "color" else ""

    if fmt == "svg":
        response = HttpResponse(svg_bytes, content_type="image/svg+xml")
        response["Content-Disposition"] = f'attachment; filename="{stem}{variant_suffix}.svg"'
        return response

    if fmt == "pdf":
        pdf_bytes = cairosvg.svg2pdf(bytestring=svg_bytes)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{stem}{variant_suffix}.pdf"'
        return response

    # PNG — high resolution (300 dpi)
    png_bytes = cairosvg.svg2png(bytestring=svg_bytes, scale=PNG_SCALE)
    response = HttpResponse(png_bytes, content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="{stem}{variant_suffix}.png"'
    return response
