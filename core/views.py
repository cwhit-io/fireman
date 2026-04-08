from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.http import urlunquote

import io

import qrcode


def index(request):
    return render(request, "core/index.html")


def homepage(request):
    return render(request, "home.html")


def qr_page(request):
    """Render a small QR generator page. The form posts text which is
    rendered via the `qr_image` endpoint below.
    """
    data = request.GET.get("data", "")
    size = request.GET.get("size", "300")
    return render(request, "core/qr.html", {"data": data, "size": size})


def qr_image(request):
    """Return a PNG QR code for the given `data` (GET param) and optional
    `size` (pixels)."""
    data = request.GET.get("data")
    if not data:
        return HttpResponseBadRequest("Missing `data` parameter")

    try:
        size = int(request.GET.get("size", 300))
    except (TypeError, ValueError):
        size = 300

    # qrcode library produces a PIL image
    qr = qrcode.QRCode(border=2)
    qr.add_data(urlunquote(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Resize to requested size preserving aspect ratio
    img = img.resize((size, size))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return HttpResponse(buf.getvalue(), content_type="image/png")
