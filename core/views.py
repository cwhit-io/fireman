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
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageColor, ImageDraw

logger = logging.getLogger(__name__)

MAX_QR_DATA_LEN = 2000
_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
_FINDER_BORDER = 4
_BODY_SHAPES = {'square', 'circle', 'rounded', 'diamond', 'vertical', 'horizontal'}
_EYE_FRAME_SHAPES = {'square', 'rounded', 'circle', 'diamond'}
_EYE_BALL_SHAPES = {'square', 'rounded', 'circle', 'diamond'}
_GRADIENT_DIRECTIONS = {'horizontal', 'vertical', 'diagonal'}


def _validate_color(value, default='#000000'):
    """Return value if it is a valid 6-digit hex color, otherwise return default."""
    if isinstance(value, str) and _COLOR_RE.match(value):
        return value
    return default


def _validate_choice(value, allowed, default):
    """Return a validated string choice from an allowlist."""
    if isinstance(value, str) and value in allowed:
        return value
    return default


def _validate_bool(value, default=False):
    """Return a bool from common truthy inputs."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'off'}:
            return False
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


def _finder_origins(matrix_size):
    """Return the top-left origins of the three finder patterns."""
    return (
        (_FINDER_BORDER, _FINDER_BORDER),
        (matrix_size - _FINDER_BORDER - 7, _FINDER_BORDER),
        (_FINDER_BORDER, matrix_size - _FINDER_BORDER - 7),
    )


def _is_finder_module(x_pos, y_pos, matrix_size):
    """Return True when a module belongs to one of the three finder regions."""
    return any(
        origin_x <= x_pos < origin_x + 7 and origin_y <= y_pos < origin_y + 7
        for origin_x, origin_y in _finder_origins(matrix_size)
    )


def _svg_rect(x_pos, y_pos, width, height, fill, radius=0):
    attrs = [
        f'x="{x_pos:.2f}"',
        f'y="{y_pos:.2f}"',
        f'width="{width:.2f}"',
        f'height="{height:.2f}"',
        f'fill="{fill}"',
    ]
    if radius > 0:
        attrs.append(f'rx="{radius:.2f}"')
        attrs.append(f'ry="{radius:.2f}"')
    return f'<rect {' '.join(attrs)}/>'


def _svg_circle(x_pos, y_pos, size, fill):
    radius = size / 2
    return (
        f'<circle cx="{x_pos + radius:.2f}" cy="{y_pos + radius:.2f}" '
        f'r="{max(radius - 0.6, 0.0):.2f}" fill="{fill}"/>'
    )


def _svg_diamond(x_pos, y_pos, size, fill):
    half = size / 2
    points = (
        f'{x_pos + half:.2f},{y_pos:.2f} '
        f'{x_pos + size:.2f},{y_pos + half:.2f} '
        f'{x_pos + half:.2f},{y_pos + size:.2f} '
        f'{x_pos:.2f},{y_pos + half:.2f}'
    )
    return f'<polygon points="{points}" fill="{fill}"/>'


def _body_shape_svg(shape, x_pos, y_pos, size, fill):
    if shape == 'circle':
        return _svg_circle(x_pos, y_pos, size, fill)
    if shape == 'rounded':
        return _svg_rect(x_pos, y_pos, size, size, fill, radius=size * 0.24)
    if shape == 'diamond':
        return _svg_diamond(x_pos, y_pos, size, fill)
    if shape == 'vertical':
        width = size * 0.42
        return _svg_rect(
            x_pos + (size - width) / 2,
            y_pos + size * 0.06,
            width,
            size * 0.88,
            fill,
            radius=width / 2,
        )
    if shape == 'horizontal':
        height = size * 0.42
        return _svg_rect(
            x_pos + size * 0.06,
            y_pos + (size - height) / 2,
            size * 0.88,
            height,
            fill,
            radius=height / 2,
        )
    return _svg_rect(x_pos, y_pos, size, size, fill)


def _eye_shape_svg(shape, x_pos, y_pos, size, fill):
    if shape == 'circle':
        return _svg_circle(x_pos, y_pos, size, fill)
    if shape == 'rounded':
        return _svg_rect(x_pos, y_pos, size, size, fill, radius=size * 0.18)
    if shape == 'diamond':
        return _svg_diamond(x_pos, y_pos, size, fill)
    return _svg_rect(x_pos, y_pos, size, size, fill)


def _draw_polygon(draw, points, fill):
    draw.polygon([(x_pos, y_pos) for x_pos, y_pos in points], fill=fill)


def _hex_to_rgb(color):
    return ImageColor.getrgb(color)


def _gradient_coordinates(direction, size=None):
    direction = _validate_choice(direction, _GRADIENT_DIRECTIONS, 'horizontal')
    if size is not None:
        s = str(size)
        if direction == 'vertical':
            return '0', '0', '0', s
        if direction == 'diagonal':
            return '0', '0', s, s
        return '0', '0', s, '0'
    if direction == 'vertical':
        return '0%', '0%', '0%', '100%'
    if direction == 'diagonal':
        return '0%', '0%', '100%', '100%'
    return '0%', '0%', '100%', '0%'


def _build_gradient_mask(size, direction):
    direction = _validate_choice(direction, _GRADIENT_DIRECTIONS, 'horizontal')
    gradient = Image.linear_gradient('L').resize((size, size), Image.Resampling.BILINEAR)
    if direction == 'horizontal':
        return gradient.transpose(Image.Transpose.ROTATE_270)
    if direction == 'diagonal':
        diagonal = Image.linear_gradient('L').resize((size * 2, size * 2), Image.Resampling.BILINEAR)
        diagonal = diagonal.rotate(45, resample=Image.Resampling.BICUBIC)
        offset = size // 2
        return diagonal.crop((offset, offset, offset + size, offset + size))
    return gradient


def _build_gradient_fill_image(size, start_color, end_color, direction):
    start_rgb = _hex_to_rgb(start_color)
    end_rgb = _hex_to_rgb(end_color)
    if start_rgb == end_rgb:
        return Image.new('RGBA', (size, size), start_rgb + (255,))
    mask = _build_gradient_mask(size, direction)
    start_img = Image.new('RGBA', (size, size), start_rgb + (255,))
    end_img = Image.new('RGBA', (size, size), end_rgb + (255,))
    return Image.composite(end_img, start_img, mask)


def _body_shape_png(draw, shape, x_pos, y_pos, size, fill):
    if shape == 'circle':
        draw.ellipse((x_pos, y_pos, x_pos + size, y_pos + size), fill=fill)
        return
    if shape == 'rounded':
        draw.rounded_rectangle(
            (x_pos, y_pos, x_pos + size, y_pos + size),
            radius=size * 0.24,
            fill=fill,
        )
        return
    if shape == 'diamond':
        _draw_polygon(
            draw,
            [
                (x_pos + size / 2, y_pos),
                (x_pos + size, y_pos + size / 2),
                (x_pos + size / 2, y_pos + size),
                (x_pos, y_pos + size / 2),
            ],
            fill,
        )
        return
    if shape == 'vertical':
        width = size * 0.42
        draw.rounded_rectangle(
            (
                x_pos + (size - width) / 2,
                y_pos + size * 0.06,
                x_pos + (size + width) / 2,
                y_pos + size * 0.94,
            ),
            radius=width / 2,
            fill=fill,
        )
        return
    if shape == 'horizontal':
        height = size * 0.42
        draw.rounded_rectangle(
            (
                x_pos + size * 0.06,
                y_pos + (size - height) / 2,
                x_pos + size * 0.94,
                y_pos + (size + height) / 2,
            ),
            radius=height / 2,
            fill=fill,
        )
        return
    draw.rectangle((x_pos, y_pos, x_pos + size, y_pos + size), fill=fill)


def _eye_shape_png(draw, shape, x_pos, y_pos, size, fill):
    if shape == 'circle':
        draw.ellipse((x_pos, y_pos, x_pos + size, y_pos + size), fill=fill)
        return
    if shape == 'rounded':
        draw.rounded_rectangle(
            (x_pos, y_pos, x_pos + size, y_pos + size),
            radius=size * 0.18,
            fill=fill,
        )
        return
    if shape == 'diamond':
        _draw_polygon(
            draw,
            [
                (x_pos + size / 2, y_pos),
                (x_pos + size, y_pos + size / 2),
                (x_pos + size / 2, y_pos + size),
                (x_pos, y_pos + size / 2),
            ],
            fill,
        )
        return
    draw.rectangle((x_pos, y_pos, x_pos + size, y_pos + size), fill=fill)


def _pdf_polygon(canvas_obj, points, fill):
    canvas_obj.setFillColor(fill)
    path = canvas_obj.beginPath()
    first_x, first_y = points[0]
    path.moveTo(first_x, first_y)
    for point_x, point_y in points[1:]:
        path.lineTo(point_x, point_y)
    path.close()
    canvas_obj.drawPath(path, fill=1, stroke=0)


def _body_shape_pdf(canvas_obj, shape, x_pos, y_pos, size, fill):
    canvas_obj.setFillColor(fill)
    if shape == 'circle':
        canvas_obj.circle(x_pos + size / 2, y_pos + size / 2, max(size / 2 - 0.6, 0.0), fill=1, stroke=0)
        return
    if shape == 'rounded':
        canvas_obj.roundRect(x_pos, y_pos, size, size, size * 0.24, fill=1, stroke=0)
        return
    if shape == 'diamond':
        _pdf_polygon(
            canvas_obj,
            [
                (x_pos + size / 2, y_pos + size),
                (x_pos + size, y_pos + size / 2),
                (x_pos + size / 2, y_pos),
                (x_pos, y_pos + size / 2),
            ],
            fill,
        )
        return
    if shape == 'vertical':
        width = size * 0.42
        canvas_obj.roundRect(
            x_pos + (size - width) / 2,
            y_pos + size * 0.06,
            width,
            size * 0.88,
            width / 2,
            fill=1,
            stroke=0,
        )
        return
    if shape == 'horizontal':
        height = size * 0.42
        canvas_obj.roundRect(
            x_pos + size * 0.06,
            y_pos + (size - height) / 2,
            size * 0.88,
            height,
            height / 2,
            fill=1,
            stroke=0,
        )
        return
    canvas_obj.rect(x_pos, y_pos, size, size, fill=1, stroke=0)


def _eye_shape_pdf(canvas_obj, shape, x_pos, y_pos, size, fill):
    canvas_obj.setFillColor(fill)
    if shape == 'circle':
        canvas_obj.circle(x_pos + size / 2, y_pos + size / 2, max(size / 2 - 0.6, 0.0), fill=1, stroke=0)
        return
    if shape == 'rounded':
        canvas_obj.roundRect(x_pos, y_pos, size, size, size * 0.18, fill=1, stroke=0)
        return
    if shape == 'diamond':
        _pdf_polygon(
            canvas_obj,
            [
                (x_pos + size / 2, y_pos + size),
                (x_pos + size, y_pos + size / 2),
                (x_pos + size / 2, y_pos),
                (x_pos, y_pos + size / 2),
            ],
            fill,
        )
        return
    canvas_obj.rect(x_pos, y_pos, size, size, fill=1, stroke=0)


def _render_svg_qr(
    matrix,
    size,
    body_shape,
    eye_frame_shape,
    eye_ball_shape,
    fg_color,
    eye_color,
    bg_color,
    gradient_enabled=False,
    gradient_color=None,
    gradient_direction='horizontal',
):
    module_size = size / len(matrix)
    body_fill = fg_color
    parts = [
        f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">',
    ]
    if gradient_enabled:
        gradient_start_x, gradient_start_y, gradient_end_x, gradient_end_y = _gradient_coordinates(gradient_direction, size)
        parts.append(
            '<defs>'
            f'<linearGradient id="qr-body-gradient" gradientUnits="userSpaceOnUse" x1="{gradient_start_x}" y1="{gradient_start_y}" '
            f'x2="{gradient_end_x}" y2="{gradient_end_y}">'
            f'<stop offset="0%" stop-color="{fg_color}"/>'
            f'<stop offset="100%" stop-color="{gradient_color}"/>'
            '</linearGradient>'
            '</defs>'
        )
        body_fill = 'url(#qr-body-gradient)'
    parts.extend([
        f'<rect width="{size}" height="{size}" fill="{bg_color}"/>',
    ])

    for y_pos, row in enumerate(matrix):
        for x_pos, cell in enumerate(row):
            if cell and not _is_finder_module(x_pos, y_pos, len(matrix)):
                parts.append(
                    _body_shape_svg(
                        body_shape,
                        x_pos * module_size,
                        y_pos * module_size,
                        module_size,
                        body_fill,
                    )
                )

    for origin_x, origin_y in _finder_origins(len(matrix)):
        frame_x = origin_x * module_size
        frame_y = origin_y * module_size
        parts.append(_eye_shape_svg(eye_frame_shape, frame_x, frame_y, module_size * 7, eye_color))
        parts.append(
            _eye_shape_svg(
                eye_frame_shape,
                frame_x + module_size,
                frame_y + module_size,
                module_size * 5,
                bg_color,
            )
        )
        parts.append(
            _eye_shape_svg(
                eye_ball_shape,
                frame_x + module_size * 2,
                frame_y + module_size * 2,
                module_size * 3,
                eye_color,
            )
        )

    parts.append('</svg>')
    return ''.join(parts)


def _render_png_qr(
    matrix,
    size,
    body_shape,
    eye_frame_shape,
    eye_ball_shape,
    fg_color,
    eye_color,
    bg_color,
    gradient_enabled=False,
    gradient_color=None,
    gradient_direction='horizontal',
):
    img = Image.new('RGBA', (size, size), bg_color)
    body_mask = Image.new('L', (size, size), 0)
    body_draw = ImageDraw.Draw(body_mask)
    eye_mask = Image.new('L', (size, size), 0)
    eye_draw = ImageDraw.Draw(eye_mask)
    module_size = size / len(matrix)

    for y_pos, row in enumerate(matrix):
        for x_pos, cell in enumerate(row):
            if cell and not _is_finder_module(x_pos, y_pos, len(matrix)):
                _body_shape_png(
                    body_draw,
                    body_shape,
                    x_pos * module_size,
                    y_pos * module_size,
                    module_size,
                    255,
                )

    for origin_x, origin_y in _finder_origins(len(matrix)):
        frame_x = origin_x * module_size
        frame_y = origin_y * module_size
        _eye_shape_png(eye_draw, eye_frame_shape, frame_x, frame_y, module_size * 7, 255)
        _eye_shape_png(
            eye_draw,
            eye_frame_shape,
            frame_x + module_size,
            frame_y + module_size,
            module_size * 5,
            0,
        )
        _eye_shape_png(
            eye_draw,
            eye_ball_shape,
            frame_x + module_size * 2,
            frame_y + module_size * 2,
            module_size * 3,
            255,
        )

    if gradient_enabled:
        body_fill = _build_gradient_fill_image(size, fg_color, gradient_color, gradient_direction)
    else:
        body_fill = Image.new('RGBA', (size, size), _hex_to_rgb(fg_color) + (255,))
    eye_fill = Image.new('RGBA', (size, size), _hex_to_rgb(eye_color) + (255,))
    transparent = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    img.alpha_composite(Image.composite(body_fill, transparent, body_mask))
    img.alpha_composite(Image.composite(eye_fill, transparent, eye_mask))

    return img


def _render_pdf_qr(
    matrix,
    size,
    body_shape,
    eye_frame_shape,
    eye_ball_shape,
    fg_color,
    eye_color,
    bg_color,
    gradient_enabled=False,
    gradient_color=None,
    gradient_direction='horizontal',
):
    if gradient_enabled:
        raster = _render_png_qr(
            matrix,
            size,
            body_shape,
            eye_frame_shape,
            eye_ball_shape,
            fg_color,
            eye_color,
            bg_color,
            gradient_enabled=True,
            gradient_color=gradient_color,
            gradient_direction=gradient_direction,
        )
        buf = io.BytesIO()
        canvas_obj = canvas.Canvas(buf, pagesize=(size, size))
        canvas_obj.drawImage(ImageReader(raster), 0, 0, width=size, height=size, mask='auto')
        canvas_obj.save()
        buf.seek(0)
        return buf.getvalue()

    buf = io.BytesIO()
    canvas_obj = canvas.Canvas(buf, pagesize=(size, size))
    canvas_obj.setFillColor(bg_color)
    canvas_obj.rect(0, 0, size, size, fill=1, stroke=0)
    module_size = size / len(matrix)

    for y_pos, row in enumerate(matrix):
        for x_pos, cell in enumerate(row):
            if cell and not _is_finder_module(x_pos, y_pos, len(matrix)):
                _body_shape_pdf(
                    canvas_obj,
                    body_shape,
                    x_pos * module_size,
                    size - (y_pos + 1) * module_size,
                    module_size,
                    fg_color,
                )

    for origin_x, origin_y in _finder_origins(len(matrix)):
        frame_x = origin_x * module_size
        frame_y = size - (origin_y + 7) * module_size
        _eye_shape_pdf(canvas_obj, eye_frame_shape, frame_x, frame_y, module_size * 7, eye_color)
        _eye_shape_pdf(
            canvas_obj,
            eye_frame_shape,
            frame_x + module_size,
            frame_y + module_size,
            module_size * 5,
            bg_color,
        )
        _eye_shape_pdf(
            canvas_obj,
            eye_ball_shape,
            frame_x + module_size * 2,
            frame_y + module_size * 2,
            module_size * 3,
            eye_color,
        )

    canvas_obj.save()
    buf.seek(0)
    return buf.getvalue()


def _build_qr(
    data,
    size,
    quality,
    style,
    fg_color,
    bg_color,
    format_type,
    logo_id=None,
    logo_position='center',
    body_shape='square',
    eye_frame_shape='square',
    eye_ball_shape='square',
    eye_color=None,
    gradient_enabled=False,
    gradient_color=None,
    gradient_direction='horizontal',
):
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
    body_shape = _validate_choice(body_shape or style, _BODY_SHAPES, 'square')
    eye_frame_shape = _validate_choice(eye_frame_shape, _EYE_FRAME_SHAPES, 'square')
    eye_ball_shape = _validate_choice(eye_ball_shape, _EYE_BALL_SHAPES, 'square')
    eye_color = _validate_color(eye_color or fg_color, default=fg_color)
    gradient_enabled = _validate_bool(gradient_enabled, default=False)
    gradient_color = _validate_color(gradient_color or fg_color, default=fg_color)
    gradient_direction = _validate_choice(gradient_direction, _GRADIENT_DIRECTIONS, 'horizontal')

    if format_type == 'svg':
        return _render_svg_qr(
            matrix,
            size,
            body_shape,
            eye_frame_shape,
            eye_ball_shape,
            fg_color,
            eye_color,
            bg_color,
            gradient_enabled=gradient_enabled,
            gradient_color=gradient_color,
            gradient_direction=gradient_direction,
        )

    elif format_type == 'pdf':
        return _render_pdf_qr(
            matrix,
            size,
            body_shape,
            eye_frame_shape,
            eye_ball_shape,
            fg_color,
            eye_color,
            bg_color,
            gradient_enabled=gradient_enabled,
            gradient_color=gradient_color,
            gradient_direction=gradient_direction,
        )

    else:  # PNG
        img = _render_png_qr(
            matrix,
            size,
            body_shape,
            eye_frame_shape,
            eye_ball_shape,
            fg_color,
            eye_color,
            bg_color,
            gradient_enabled=gradient_enabled,
            gradient_color=gradient_color,
            gradient_direction=gradient_direction,
        )

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
    body_shape = _validate_choice(body.get('body_shape', style), _BODY_SHAPES, 'square')
    eye_frame_shape = _validate_choice(body.get('eye_frame_shape'), _EYE_FRAME_SHAPES, 'square')
    eye_ball_shape = _validate_choice(body.get('eye_ball_shape'), _EYE_BALL_SHAPES, 'square')
    fg_color = _validate_color(body.get('fg_color', '#000000'))
    eye_color = _validate_color(body.get('eye_color', fg_color), default=fg_color)
    bg_color = _validate_color(body.get('bg_color', '#FFFFFF'), default='#FFFFFF')
    gradient_enabled = _validate_bool(body.get('gradient_enabled', False), default=False)
    gradient_color = _validate_color(body.get('gradient_color', fg_color), default=fg_color)
    gradient_direction = _validate_choice(body.get('gradient_direction'), _GRADIENT_DIRECTIONS, 'horizontal')
    format_type = body.get('format', 'png')
    if format_type not in ('png', 'svg', 'pdf'):
        format_type = 'png'
    logo_id = body.get('logo_id')
    logo_position = body.get('logo_position', 'center')

    try:
        result = _build_qr(
            qr_data,
            size,
            quality,
            style,
            fg_color,
            bg_color,
            format_type,
            logo_id=logo_id,
            logo_position=logo_position,
            body_shape=body_shape,
            eye_frame_shape=eye_frame_shape,
            eye_ball_shape=eye_ball_shape,
            eye_color=eye_color,
            gradient_enabled=gradient_enabled,
            gradient_color=gradient_color,
            gradient_direction=gradient_direction,
        )
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
    body_shape = _validate_choice(request.GET.get("body_shape", style), _BODY_SHAPES, 'square')
    eye_frame_shape = _validate_choice(request.GET.get("eye_frame_shape"), _EYE_FRAME_SHAPES, 'square')
    eye_ball_shape = _validate_choice(request.GET.get("eye_ball_shape"), _EYE_BALL_SHAPES, 'square')
    fg_color = _validate_color(request.GET.get("fg_color", "#000000"))
    eye_color = _validate_color(request.GET.get("eye_color", fg_color), default=fg_color)
    bg_color = _validate_color(request.GET.get("bg_color", "#FFFFFF"), default="#FFFFFF")
    gradient_enabled = _validate_bool(request.GET.get("gradient_enabled", False), default=False)
    gradient_color = _validate_color(request.GET.get("gradient_color", fg_color), default=fg_color)
    gradient_direction = _validate_choice(request.GET.get("gradient_direction"), _GRADIENT_DIRECTIONS, 'horizontal')
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
        result = _build_qr(
            data,
            size,
            quality,
            style,
            fg_color,
            bg_color,
            format_type,
            logo_id=logo_id,
            logo_position=logo_position,
            body_shape=body_shape,
            eye_frame_shape=eye_frame_shape,
            eye_ball_shape=eye_ball_shape,
            eye_color=eye_color,
            gradient_enabled=gradient_enabled,
            gradient_color=gradient_color,
            gradient_direction=gradient_direction,
        )
    except Exception as e:
        logger.warning("QR code generation failed: %s", e)
        return HttpResponseBadRequest("Invalid data for QR code generation")

    content_types = {'png': 'image/png', 'svg': 'image/svg+xml', 'pdf': 'application/pdf'}
    return HttpResponse(result, content_type=content_types[format_type])
