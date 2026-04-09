from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.conf import settings
from urllib.parse import unquote as urlunquote

import io
import logging
import os
import re
import uuid
import json
import base64

import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

MAX_QR_DATA_LEN = 2000
_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def _validate_color(value, default='#000000'):
    """Return value if it is a valid 6-digit hex color, otherwise return default."""
    if isinstance(value, str) and _COLOR_RE.match(value):
        return value
    return default


def index(request):
    return render(request, "core/index.html")


def homepage(request):
    return render(request, "home.html")


def links_page(request):
    return render(request, "core/links.html")


def qr_page(request):
    """Render the QR generator page."""
    return render(request, "core/qr.html")


def _apply_circular_style(img, matrix):
    """Apply circular style to QR code modules."""
    draw = ImageDraw.Draw(img)
    size_per_module = img.size[0] // len(matrix)

    # Clear image
    img = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                x_pos = x * size_per_module
                y_pos = y * size_per_module
                cx = x_pos + size_per_module // 2
                cy = y_pos + size_per_module // 2
                r = size_per_module // 2 - 1
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 255))

    return img


def _apply_rounded_style(img, matrix):
    """Apply rounded style to QR code modules."""
    draw = ImageDraw.Draw(img)
    size_per_module = img.size[0] // len(matrix)

    # Clear image
    img = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                x_pos = x * size_per_module
                y_pos = y * size_per_module
                rx = size_per_module // 4
                draw.rounded_rectangle([x_pos, y_pos, x_pos + size_per_module, y_pos + size_per_module], radius=rx, fill=(0, 0, 0, 255))

    return img


def _add_logo_to_qr(qr_img, logo_id, position, size):
    """Add logo to QR code image."""
    try:
        # Find the logo file
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_logos')
        logo_files = [f for f in os.listdir(temp_dir) if f.startswith(logo_id)]

        if not logo_files:
            logger.warning("Logo file not found for ID: %s", logo_id)
            return qr_img

        logo_path = os.path.join(temp_dir, logo_files[0])

        # Load and resize logo
        logo = Image.open(logo_path).convert('RGBA')
        logo_size = size // 4
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # Position the logo
        if position == "top":
            x = (size - logo_size) // 2
            y = size // 8
        elif position == "bottom":
            x = (size - logo_size) // 2
            y = size - size // 8 - logo_size
        else:  # center
            x = (size - logo_size) // 2
            y = (size - logo_size) // 2

        # Composite logo onto QR code
        qr_img.paste(logo, (x, y), logo)

        return qr_img
    except Exception as e:
        logger.warning("Failed to add logo to QR code: %s", e)
        return qr_img


def _build_qr(data, size, quality, style, fg_color, bg_color, format_type,
              logo_id=None, logo_position='center'):
    """Build a QR code and return its content.

    Returns bytes for PNG and PDF formats, str for SVG.
    Colors must already be validated hex strings before calling this function.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=quality,
        border=4,
    )
    qr.add_data(urlunquote(data))
    qr.make(fit=True)
    matrix = qr.get_matrix()

    if format_type == 'svg':
        size_per_module = size // len(matrix)
        parts = [
            f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">',
            f'<rect width="{size}" height="{size}" fill="{bg_color}"/>',
        ]
        for y, row in enumerate(matrix):
            for x, cell in enumerate(row):
                if cell:
                    xp = x * size_per_module
                    yp = y * size_per_module
                    if style == 'circle':
                        cx = xp + size_per_module // 2
                        cy = yp + size_per_module // 2
                        r = size_per_module // 2 - 1
                        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fg_color}"/>')
                    elif style == 'rounded':
                        rx = size_per_module // 4
                        parts.append(
                            f'<rect x="{xp}" y="{yp}" width="{size_per_module}" '
                            f'height="{size_per_module}" rx="{rx}" ry="{rx}" fill="{fg_color}"/>'
                        )
                    else:
                        parts.append(
                            f'<rect x="{xp}" y="{yp}" width="{size_per_module}" '
                            f'height="{size_per_module}" fill="{fg_color}"/>'
                        )
        parts.append('</svg>')
        return ''.join(parts)

    elif format_type == 'pdf':
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(size, size))
        c.setFillColor(bg_color)
        c.rect(0, 0, size, size, fill=1)
        spm = size // len(matrix)
        c.setFillColor(fg_color)
        for y, row in enumerate(matrix):
            for x, cell in enumerate(row):
                if cell:
                    xp = x * spm
                    yp = size - (y + 1) * spm  # PDF Y-axis is bottom-up
                    if style == 'circle':
                        cx = xp + spm // 2
                        cy = yp + spm // 2
                        c.circle(cx, cy, spm // 2 - 1, fill=1)
                    elif style == 'rounded':
                        c.roundRect(xp, yp, spm, spm, spm // 4, fill=1)
                    else:
                        c.rect(xp, yp, spm, spm, fill=1)
        c.save()
        buf.seek(0)
        return buf.getvalue()

    else:  # PNG
        if style == 'circle':
            img = Image.new('RGBA', (len(matrix) * quality, len(matrix) * quality), (255, 255, 255, 0))
            img = _apply_circular_style(img, matrix)
        elif style == 'rounded':
            img = Image.new('RGBA', (len(matrix) * quality, len(matrix) * quality), (255, 255, 255, 0))
            img = _apply_rounded_style(img, matrix)
        else:
            img = qr.make_image(fill_color=fg_color, back_color=bg_color).convert('RGBA')

        img = img.resize((size, size), Image.Resampling.LANCZOS)

        if logo_id:
            img = _add_logo_to_qr(img, logo_id, logo_position, size)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf.getvalue()


def api_generate_preview(request):
    """API endpoint for generating QR code previews."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    qr_data = body.get('data', '').strip()
    if not qr_data:
        return JsonResponse({'error': 'Missing data parameter'}, status=400)
    if len(qr_data) > MAX_QR_DATA_LEN:
        return JsonResponse({'error': 'Data too long (max 2000 characters)'}, status=400)

    try:
        size = int(body.get('size', 300))
        if size < 50 or size > 2000:
            size = 300
    except (TypeError, ValueError):
        size = 300

    try:
        quality = int(body.get('quality', 10))
        if quality < 5 or quality > 20:
            quality = 10
    except (TypeError, ValueError):
        quality = 10

    style = body.get('style', 'square')
    fg_color = _validate_color(body.get('fg_color', '#000000'))
    bg_color = _validate_color(body.get('bg_color', '#FFFFFF'), default='#FFFFFF')
    format_type = body.get('format', 'png')
    if format_type not in ('png', 'svg', 'pdf'):
        format_type = 'png'
    logo_id = body.get('logo_id')
    logo_position = body.get('logo_position', 'center')

    try:
        result = _build_qr(qr_data, size, quality, style, fg_color, bg_color,
                           format_type, logo_id=logo_id, logo_position=logo_position)
    except Exception as e:
        logger.error("API preview generation failed: %s", e)
        return JsonResponse({'error': 'Failed to generate preview'}, status=500)

    if format_type == 'svg':
        return JsonResponse({'format': 'svg', 'data': result, 'mime': 'image/svg+xml'})
    elif format_type == 'pdf':
        b64 = base64.b64encode(result).decode('utf-8')
        return JsonResponse({
            'format': 'pdf',
            'data': f'data:application/pdf;base64,{b64}',
            'mime': 'application/pdf',
        })
    else:  # PNG
        b64 = base64.b64encode(result).decode('utf-8')
        return JsonResponse({
            'format': 'png',
            'data': f'data:image/png;base64,{b64}',
            'mime': 'image/png',
        })


def upload_logo(request):
    """Handle logo upload and return a temporary ID."""
    if request.method == 'POST' and request.FILES.get('logo'):
        logo_file = request.FILES['logo']

        # Reject SVG outright (can contain embedded scripts)
        if logo_file.content_type == 'image/svg+xml':
            return JsonResponse({'error': 'SVG files are not allowed'}, status=400)

        # Validate Content-Type header
        if not logo_file.content_type.startswith('image/'):
            return JsonResponse({'error': 'Invalid file type'}, status=400)

        # Read file content into memory and verify it's a real image via PIL
        file_bytes = logo_file.read()
        try:
            img_check = Image.open(io.BytesIO(file_bytes))
            img_check.verify()
        except Exception:
            return JsonResponse({'error': 'File is not a valid image'}, status=400)

        # Generate temporary ID and save
        logo_id = str(uuid.uuid4())
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_logos')
        os.makedirs(temp_dir, exist_ok=True)

        # Sanitize filename: keep only alphanumeric, dots, hyphens, underscores
        safe_name = re.sub(r'[^\w.\-]', '_', logo_file.name)
        file_path = os.path.join(temp_dir, f"{logo_id}_{safe_name}")
        with open(file_path, 'wb') as destination:
            destination.write(file_bytes)

        return JsonResponse({'logo_id': logo_id, 'filename': logo_file.name})

    return JsonResponse({'error': 'No file uploaded'}, status=400)


# Explicit allowlist — only these filenames may be downloaded; no user-supplied paths.
_PRINTER_DRIVERS = {
    "mac": "KM_IC419_v3_0_FD702.dmg",
    "win": "KM_IC419_v3_0_FD703_WinRel1.zip",
}


def printer_driver_download(request, platform):
    """Serve a printer driver file identified by an allowlisted platform key."""
    filename = _PRINTER_DRIVERS.get(platform)
    if not filename:
        from django.http import Http404
        raise Http404

    file_path = settings.ASSETS_DIR / "printer" / filename
    if not file_path.exists():
        from django.http import Http404
        raise Http404

    import mimetypes
    from django.http import FileResponse
    mime_type, _ = mimetypes.guess_type(str(file_path))
    response = FileResponse(
        open(file_path, "rb"),
        content_type=mime_type or "application/octet-stream",
        as_attachment=True,
        filename=filename,
    )
    return response


def qr_image(request):
    """Return a QR code for the given `data` (GET param) and optional parameters."""
    data = request.GET.get("data")
    if not data:
        return HttpResponseBadRequest("Missing `data` parameter")
    if len(data) > MAX_QR_DATA_LEN:
        return HttpResponseBadRequest("Data too long (max 2000 characters)")

    format_type = request.GET.get("format", "png").lower()
    if format_type not in ["png", "svg", "pdf"]:
        format_type = "png"

    style = request.GET.get("style", "square")
    fg_color = _validate_color(request.GET.get("fg_color", "#000000"))
    bg_color = _validate_color(request.GET.get("bg_color", "#FFFFFF"), default="#FFFFFF")
    logo_position = request.GET.get("logo_position", "center")

    try:
        size = int(request.GET.get("size", 300))
        if size < 50 or size > 2000:
            size = 300
    except (TypeError, ValueError):
        size = 300

    try:
        quality = int(request.GET.get("quality", 10))
        if quality < 5 or quality > 20:
            quality = 10
    except (TypeError, ValueError):
        quality = 10

    logo_id = request.GET.get("logo_id") or None

    try:
        result = _build_qr(data, size, quality, style, fg_color, bg_color,
                           format_type, logo_id=logo_id, logo_position=logo_position)
    except Exception as e:
        logger.warning("QR code generation failed: %s", e)
        return HttpResponseBadRequest("Invalid data for QR code generation")

    content_types = {'png': 'image/png', 'svg': 'image/svg+xml', 'pdf': 'application/pdf'}
    return HttpResponse(result, content_type=content_types[format_type])
