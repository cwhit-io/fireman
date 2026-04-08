import io
import os
import re
import tempfile
import uuid

import qrcode
import qrcode.image.svg
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from PIL import Image
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas

# Directory for temporary logo uploads (cleaned up on download)
_TMP_DIR = tempfile.gettempdir()

# Regex to validate a simple hex color: #rrggbb or #rgb
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$")


def _sanitize_color(value, default):
    """Return value if it looks like a valid hex color, else default."""
    v = (value or "").strip()
    return v if _HEX_COLOR_RE.match(v) else default


def _sanitize_text(text, max_len=2048):
    """Strip and truncate to avoid abuse."""
    return (text or "").strip()[:max_len]


def _logo_tmp_path(logo_id):
    """Return the path for a stored temporary logo."""
    # Allow only alphanumeric + dash to prevent path traversal
    safe_id = re.sub(r"[^a-zA-Z0-9\-]", "", logo_id)
    return os.path.join(_TMP_DIR, f"qr_logo_{safe_id}")


def _save_tmp_logo(logo_file):
    """Save uploaded logo to a temp file and return its id."""
    logo_id = str(uuid.uuid4())
    path = _logo_tmp_path(logo_id)
    with open(path, "wb") as f:
        for chunk in logo_file.chunks():
            f.write(chunk)
    return logo_id


def _make_qr_pil(text, fg_color, bg_color, logo_path=None):
    """
    Generate a QR code as a PIL RGBA image.
    Uses high error-correction (H) when a logo is embedded so the code
    remains scannable even with the centre obscured.
    """
    ec = (
        qrcode.constants.ERROR_CORRECT_H
        if logo_path
        else qrcode.constants.ERROR_CORRECT_M
    )
    qr = qrcode.QRCode(error_correction=ec, box_size=10, border=4)
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        fill_color=fg_color,
        back_color=bg_color,
    ).convert("RGBA")

    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        qr_w, qr_h = img.size
        logo_max = int(min(qr_w, qr_h) * 0.22)
        logo.thumbnail((logo_max, logo_max), Image.LANCZOS)
        lw, lh = logo.size
        pad = 6
        bg = Image.new("RGBA", (lw + pad * 2, lh + pad * 2), "white")
        bg.paste(logo, (pad, pad), logo)
        bw, bh = bg.size
        pos = ((qr_w - bw) // 2, (qr_h - bh) // 2)
        img.paste(bg, pos, bg)

    return img


def _make_qr_svg_bytes(text, fg_color, bg_color):
    """Return SVG bytes for the QR code."""
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)

    factory = qrcode.image.svg.SvgPathFillImage
    img = qr.make_image(image_factory=factory, fill_color=fg_color)

    buf = io.BytesIO()
    img.save(buf)
    svg_bytes = buf.getvalue()

    # Inject background rect after the opening <svg ...> tag
    if bg_color.lower() not in ("#ffffff", "#fff", "white"):
        svg_str = svg_bytes.decode()
        svg_open_end = svg_str.index(">", svg_str.index("<svg")) + 1
        vb = re.search(r'viewBox="([^"]+)"', svg_str)
        if vb:
            parts = vb.group(1).split()
            if len(parts) == 4:
                w, h = parts[2], parts[3]
                rect = f'<rect width="{w}" height="{h}" fill="{bg_color}"/>'
                svg_str = svg_str[:svg_open_end] + rect + svg_str[svg_open_end:]
        svg_bytes = svg_str.encode()

    return svg_bytes


def _make_qr_pdf_bytes(text, fg_color, bg_color, logo_path=None):
    """Return PDF bytes with a print-ready QR code (3 x 3 inches at 300 DPI)."""
    pil_img = _make_qr_pil(text, fg_color, bg_color, logo_path)

    # Render at 300 DPI -> 900 x 900 px
    target_px = 900
    pil_img = pil_img.resize((target_px, target_px), Image.LANCZOS)

    # Convert to RGB for embedding in PDF
    bg_rgb = bg_color if bg_color else "white"
    rgb_img = Image.new("RGB", pil_img.size, bg_rgb)
    rgb_img.paste(pil_img, mask=pil_img.split()[3])

    png_buf = io.BytesIO()
    rgb_img.save(png_buf, format="PNG")
    png_buf.seek(0)

    pdf_buf = io.BytesIO()
    page_w, page_h = letter  # 8.5 x 11 in
    c = rl_canvas.Canvas(pdf_buf, pagesize=(page_w, page_h))

    qr_size = 3 * inch
    x = (page_w - qr_size) / 2
    y = (page_h - qr_size) / 2

    # White/bg page background
    try:
        c.setFillColor(HexColor(bg_rgb))
    except Exception:
        c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    c.drawImage(png_buf, x, y, width=qr_size, height=qr_size, mask="auto")
    c.save()
    return pdf_buf.getvalue()


class QRCodeGeneratorView(View):
    """Main QR code generator page."""

    def get(self, request):
        return render(request, "qrcode/generator.html")


class QRCodePreviewView(View):
    """
    htmx target: receives form POST, returns SVG preview partial + hidden
    fields for subsequent download requests.
    """

    def post(self, request):
        text = _sanitize_text(request.POST.get("text", ""))
        fg_color = _sanitize_color(request.POST.get("fg_color", ""), "#000000")
        bg_color = _sanitize_color(request.POST.get("bg_color", ""), "#ffffff")

        if not text:
            return HttpResponse(
                '<p class="text-error text-sm">Please enter text or a URL.</p>'
            )

        # Handle logo upload or re-use existing temp id
        logo_id = ""
        logo_path = None
        logo_file = request.FILES.get("logo")
        if logo_file:
            logo_id = _save_tmp_logo(logo_file)
            logo_path = _logo_tmp_path(logo_id)
        else:
            prev_logo_id = request.POST.get("logo_id", "")
            if prev_logo_id:
                candidate = _logo_tmp_path(prev_logo_id)
                if os.path.exists(candidate):
                    logo_id = prev_logo_id
                    logo_path = candidate

        svg_bytes = _make_qr_svg_bytes(text, fg_color, bg_color)
        svg_data = svg_bytes.decode()

        ctx = {
            "svg_data": svg_data,
            "text": text,
            "fg_color": fg_color,
            "bg_color": bg_color,
            "logo_id": logo_id,
        }
        return render(request, "qrcode/_preview.html", ctx)


class QRCodeDownloadView(View):
    """
    Returns the QR code as a downloadable file.
    Expects POST fields: text, fg_color, bg_color, logo_id, fmt (png|svg|pdf).
    """

    def post(self, request):
        text = _sanitize_text(request.POST.get("text", ""))
        fg_color = _sanitize_color(request.POST.get("fg_color", ""), "#000000")
        bg_color = _sanitize_color(request.POST.get("bg_color", ""), "#ffffff")
        fmt = request.POST.get("fmt", "png").lower()
        if fmt not in ("png", "svg", "pdf"):
            fmt = "png"

        if not text:
            return HttpResponse("No text provided.", status=400)

        logo_id = request.POST.get("logo_id", "")
        logo_path = None
        if logo_id:
            candidate = _logo_tmp_path(logo_id)
            if os.path.exists(candidate):
                logo_path = candidate

        if fmt == "svg":
            data = _make_qr_svg_bytes(text, fg_color, bg_color)
            return HttpResponse(
                data,
                content_type="image/svg+xml",
                headers={"Content-Disposition": 'attachment; filename="qrcode.svg"'},
            )

        if fmt == "pdf":
            data = _make_qr_pdf_bytes(text, fg_color, bg_color, logo_path)
            return HttpResponse(
                data,
                content_type="application/pdf",
                headers={"Content-Disposition": 'attachment; filename="qrcode.pdf"'},
            )

        # Default: PNG at 300 DPI (900 x 900 px)
        pil_img = _make_qr_pil(text, fg_color, bg_color, logo_path)
        pil_img = pil_img.resize((900, 900), Image.LANCZOS)
        bg_rgb = bg_color if bg_color else "white"
        rgb_img = Image.new("RGB", pil_img.size, bg_rgb)
        rgb_img.paste(pil_img, mask=pil_img.split()[3])
        buf = io.BytesIO()
        rgb_img.save(buf, format="PNG", dpi=(300, 300))
        return HttpResponse(
            buf.getvalue(),
            content_type="image/png",
            headers={"Content-Disposition": 'attachment; filename="qrcode.png"'},
        )
