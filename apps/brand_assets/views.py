import os
import re

import cairosvg
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
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


def _download_url(request, asset, fmt="svg", variant="color"):
    path = reverse("brand_assets:download", args=[asset.pk])
    return request.build_absolute_uri(f"{path}?format={fmt}&variant={variant}")


def _asset_payload(request, asset):
    return {
        "id": asset.pk,
        "name": asset.name,
        "description": asset.description,
        "category": asset.category.name if asset.category else None,
        "svg": request.build_absolute_uri(asset.svg_file.url),
        "downloads": {
            fmt: {
                variant: _download_url(request, asset, fmt, variant)
                for variant in ("color", "black", "white")
            }
            for fmt in ("svg", "pdf", "png")
        },
    }


def _ordered_assets():
    """Assets in the same order as the HTML page: categorised, then uncategorised."""
    categories = BrandAssetCategory.objects.prefetch_related("assets").order_by("order", "name")
    assets = []
    for category in categories:
        assets.extend(category.assets.all())
    assets.extend(BrandAsset.objects.filter(category__isnull=True).order_by("order", "name"))
    return assets


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


@require_GET
def brand_assets_json(request):
    """Machine-readable index of every brand asset and colour."""
    assets = [_asset_payload(request, asset) for asset in _ordered_assets()]
    colors = [
        {
            "name": color.name,
            "hex": color.hex_value,
            "rgb": color.rgb_label,
            "cmyk": color.cmyk_label,
            "pantone": color.pantone_label,
        }
        for color in BrandColor.objects.order_by("order", "name")
    ]
    response = JsonResponse({
        "name": "Ember Brand Assets",
        "description": "Official Ember logos and brand colours.",
        "page": request.build_absolute_uri(reverse("brand_assets:index")),
        "llms_txt": request.build_absolute_uri(reverse("brand_assets:llms_txt")),
        "assets": assets,
        "colors": colors,
    })
    response["Cache-Control"] = "public, max-age=300"
    return response


@require_GET
def brand_assets_llms_txt(request):
    """Plain-text brand asset summary following the llms.txt convention."""
    page_url = request.build_absolute_uri(reverse("brand_assets:index"))
    json_url = request.build_absolute_uri(reverse("brand_assets:index_json"))

    lines = [
        "# Ember Brand Assets",
        "",
        "> Official Ember logos, marks, and brand colours. Assets are available as SVG, "
        "PDF, and 300 dpi PNG, in colour, black, and white variants.",
        "",
        f"HTML page: {page_url}",
        f"Machine-readable JSON: {json_url}",
        "",
        "## Logos and Marks",
        "",
    ]

    assets = _ordered_assets()
    if not assets:
        lines.append("No brand assets are currently published.")
    for asset in assets:
        lines.append(f"### {asset.name}")
        lines.append("")
        if asset.description:
            lines.append(asset.description)
            lines.append("")
        if asset.category:
            lines.append(f"Category: {asset.category.name}")
        lines.append(f"- SVG (colour): {_download_url(request, asset, 'svg', 'color')}")
        lines.append(f"- PNG, 300 dpi (colour): {_download_url(request, asset, 'png', 'color')}")
        lines.append(f"- PDF (colour): {_download_url(request, asset, 'pdf', 'color')}")
        lines.append(
            "- Black and white variants: append `&variant=black` or `&variant=white` "
            "to any download URL above."
        )
        lines.append("")

    colors = BrandColor.objects.order_by("order", "name")
    if colors:
        lines.append("## Brand Colours")
        lines.append("")
        for color in colors:
            details = [color.hex_value]
            if color.rgb_label:
                details.append(color.rgb_label)
            if color.cmyk_label:
                details.append(color.cmyk_label)
            if color.pantone_label:
                details.append(color.pantone_label)
            lines.append(f"- {color.name}: {', '.join(details)}")
        lines.append("")

    response = HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "public, max-age=300"
    return response


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
    except Exception as exc:
        raise Http404("Asset file not found.") from exc

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
