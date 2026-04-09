import json
import re
from io import BytesIO

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas as rl_canvas

from .models import POINTS_PER_INCH, ImpositionTemplate, PrintSize, ProductCategory

# Muted background colours cycled per category
_GROUP_COLORS = [
    "#4d8ccd",  # Soft Blue — Trustworthy and calm (primary)
    "#ff6b6b",  # Coral — Warmth and urgency (secondary)
    "#3ecf8e",  # Muted Mint Green — Success and confirmation (accent)
    "#eaa63b",  # Muted Orange — Warm warning (for alerts)
    "#305780",  # Darker Blue — Reliable alternative (for depth)
    "#af2b1d",  # Muted Red — Clear error indication (emergency)
    "#7c1e14",  # Dark Coral — Stronger secondary focus (hover state)
    "#a88d22",  # Muted Amber — Friendly warmth (for highlights)
]




def print_templates(request):
    """Public page listing all cut sizes grouped by category."""
    sizes_qs = (
        PrintSize.objects.filter(
            size_type__in=[PrintSize.SizeType.CUT, PrintSize.SizeType.BOTH],
            is_published=True,
        )
        .select_related("category")
        .order_by("category__name", "name")
    )

    # Build a list of (category_name, [sizes]) groups.
    # Sizes with no category are collected under None → displayed last as "Other".
    groups: dict[str | None, list] = {}
    for size in sizes_qs:
        key = size.category.name if size.category_id else None
        groups.setdefault(key, []).append(size)

    # Sort: named categories first (alphabetical), uncategorised last
    named = sorted(
        ((k, v) for k, v in groups.items() if k is not None), key=lambda t: t[0]
    )
    if None in groups:
        named.append((None, groups[None]))

    # Attach a background colour to each group
    sorted_groups = [
        (name, sizes, _GROUP_COLORS[i % len(_GROUP_COLORS)])
        for i, (name, sizes) in enumerate(named)
    ]

    return render(
        request,
        "impose/print_templates.html",
        {"groups": sorted_groups},
    )


_BLEED_PT = 9.0  # 0.125 in


def print_size_template_pdf(request, pk, orientation):
    """Generate and download a PDF template with cut size + 0.125in bleed guides."""
    if orientation not in ("portrait", "landscape"):
        raise Http404

    size = get_object_or_404(PrintSize, pk=pk)

    cut_w = float(size.width)
    cut_h = float(size.height)

    if orientation == "landscape":
        cut_w, cut_h = max(cut_w, cut_h), min(cut_w, cut_h)
    else:
        cut_w, cut_h = min(cut_w, cut_h), max(cut_w, cut_h)

    bleed = _BLEED_PT
    safe = _BLEED_PT  # 0.125 in safe zone inside cut line

    page_w = cut_w + 2 * bleed
    page_h = cut_h + 2 * bleed

    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))

    # Bleed zone background
    c.setFillColor(HexColor("#FFCCCC"))
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Cut area (white)
    c.setFillColor(white)
    c.rect(bleed, bleed, cut_w, cut_h, fill=1, stroke=0)

    # Cut line — red dashed
    c.setStrokeColor(HexColor("#FF0000"))
    c.setLineWidth(0.5)
    c.setDash([3, 2])
    c.rect(bleed, bleed, cut_w, cut_h, fill=0, stroke=1)
    c.setDash()

    # Safe zone — blue dashed
    c.setStrokeColor(HexColor("#0055FF"))
    c.setLineWidth(0.4)
    c.setDash([2, 3])
    c.rect(bleed + safe, bleed + safe, cut_w - 2 * safe, cut_h - 2 * safe, fill=0, stroke=1)
    c.setDash()

    # Centre label
    c.setFillColor(HexColor("#999999"))
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(page_w / 2, page_h / 2 + 4, size.name)
    c.setFont("Helvetica", 5.5)
    c.drawCentredString(
        page_w / 2,
        page_h / 2 - 4,
        '{w}" \u00d7 {h}"  +  0.125" bleed  \u2022  {o}'.format(
            w=f"{cut_w / 72:g}", h=f"{cut_h / 72:g}", o=orientation
        ),
    )

    # Legend — bottom-left, inside safe zone
    c.setFont("Helvetica", 4)
    c.setFillColor(HexColor("#FF0000"))
    c.drawString(bleed + safe + 2, bleed + safe + 3, "- Cut line")
    c.setFillColor(HexColor("#0055FF"))
    c.drawString(bleed + safe + 2, bleed + safe + 9, "- Safe zone")

    c.showPage()
    c.save()

    safe_name = re.sub(r"[^\w\-]", "_", size.name)
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        'attachment; filename="{n}_{o}_template.pdf"'.format(n=safe_name, o=orientation)
    )
    return response


# ── JSON export / import helpers ─────────────────────────────────────────────

EXPORT_VERSION = 1

_PT_FIELDS = [
    "cut_width",
    "cut_height",
    "sheet_width",
    "sheet_height",
    "bleed",
    "margin_top",
    "margin_right",
    "margin_bottom",
    "margin_left",
    "barcode_x",
    "barcode_y",
    "barcode_width",
    "barcode_height",
]
_PLAIN_FIELDS = ["name", "columns", "rows", "notes", "print_barcode", "allow_mailmerge"]


def _template_to_dict(tmpl: ImpositionTemplate) -> dict:
    """Serialise one template to a plain dict (dimensions in inches)."""
    d = {f: getattr(tmpl, f) for f in _PLAIN_FIELDS}
    for f in _PT_FIELDS:
        val = getattr(tmpl, f)
        d[f] = round(float(val) / POINTS_PER_INCH, 6) if val is not None else None
    # Export product_category by name so it can be resolved on import
    d["product_category"] = (
        tmpl.product_category.name if tmpl.product_category else None
    )
    return d


def _dict_to_template_fields(d: dict) -> dict:
    """Convert an exported dict back to model kwargs (dimensions in points)."""
    fields = {f: d.get(f) for f in _PLAIN_FIELDS}
    for f in _PT_FIELDS:
        val = d.get(f)
        fields[f] = round(float(val) * POINTS_PER_INCH, 3) if val is not None else None
    # non-nullable fields default to 0
    for f in ["bleed", "margin_top", "margin_right", "margin_bottom", "margin_left"]:
        if fields[f] is None:
            fields[f] = 0
    for f in ["barcode_width", "barcode_height"]:
        if fields[f] is None:
            fields[f] = 90.0 if f == "barcode_width" else 25.2
    # Boolean field — default to True for legacy exports that pre-date the field
    if fields.get("print_barcode") is None:
        fields["print_barcode"] = True
    # Boolean field — default to False for legacy exports
    if fields.get("allow_mailmerge") is None:
        fields["allow_mailmerge"] = False
    # Resolve product_category name → FK id
    cat_name = d.get("product_category") or ""
    if cat_name:
        from .models import ProductCategory

        cat = ProductCategory.objects.filter(name=cat_name).first()
        fields["product_category_id"] = cat.pk if cat else None
    else:
        fields["product_category_id"] = None
    return fields


def _pts_to_in(pts):
    """Convert points to inches, rounded to 4 decimal places."""
    if pts is None:
        return ""
    return round(float(pts) / POINTS_PER_INCH, 4)


def _in_to_pts(inches_str):
    """Convert inches string to points. Returns None if blank/invalid."""
    s = (inches_str or "").strip()
    if not s:
        return None
    try:
        return float(s) * POINTS_PER_INCH
    except (ValueError, TypeError):
        return None


def _build_form_context():
    from apps.cutter.models import CutterProgram
    from apps.routing.models import RoutingPreset

    from .models import PrintSize, ProductCategory

    return {
        "cutter_programs": CutterProgram.objects.filter(active=True).order_by("name"),
        "routing_presets": RoutingPreset.objects.filter(active=True).order_by("name"),
        "product_categories": ProductCategory.objects.order_by("name"),
        "cut_sizes": PrintSize.objects.filter(
            size_type__in=[PrintSize.SizeType.CUT, PrintSize.SizeType.BOTH]
        ).order_by("name"),
        "sheet_sizes": PrintSize.objects.filter(
            size_type__in=[PrintSize.SizeType.SHEET, PrintSize.SizeType.BOTH]
        ).order_by("name"),
    }


def _get_initial_form_values(tmpl=None):
    if tmpl:
        return {
            "name": tmpl.name,
            "product_category": str(tmpl.product_category_id)
            if tmpl.product_category_id
            else "",
            "cut_size": str(tmpl.cut_size_id) if tmpl.cut_size_id else "",
            "sheet_size": str(tmpl.sheet_size_id) if tmpl.sheet_size_id else "",
            "cut_width": _pts_to_in(tmpl.cut_width)
            if tmpl.cut_width is not None
            else "",
            "cut_height": _pts_to_in(tmpl.cut_height)
            if tmpl.cut_height is not None
            else "",
            "sheet_width": _pts_to_in(tmpl.sheet_width),
            "sheet_height": _pts_to_in(tmpl.sheet_height),
            "bleed": _pts_to_in(tmpl.bleed),
            "columns": str(tmpl.columns),
            "rows": str(tmpl.rows),
            "barcode_x": _pts_to_in(tmpl.barcode_x)
            if tmpl.barcode_x is not None
            else "",
            "barcode_y": _pts_to_in(tmpl.barcode_y)
            if tmpl.barcode_y is not None
            else "",
            "barcode_width": _pts_to_in(tmpl.barcode_width),
            "barcode_height": _pts_to_in(tmpl.barcode_height),
            "print_barcode": tmpl.print_barcode,
            "allow_mailmerge": tmpl.allow_mailmerge,
            "cutter_program": str(tmpl.cutter_program_id)
            if tmpl.cutter_program_id
            else "",
            "routing_preset": str(tmpl.routing_preset_id)
            if tmpl.routing_preset_id
            else "",
            "notes": tmpl.notes,
        }
    return {
        "name": "",
        "product_category": "",
        "cut_size": "",
        "sheet_size": "",
        "cut_width": "",
        "cut_height": "",
        "sheet_width": "",
        "sheet_height": "",
        "bleed": "0.125",
        "columns": "1",
        "rows": "1",
        "barcode_x": "",
        "barcode_y": "",
        "barcode_width": "1.25",  # DC-646 default: 1.25" wide (3-digit Code 39)
        "barcode_height": "0.35",  # DC-646 default: 0.35" tall
        "print_barcode": True,
        "allow_mailmerge": False,
        "cutter_program": "",
        "routing_preset": "",
        "notes": "",
    }


def _validate_template_form(data):
    errors = {}
    if not data.get("name", "").strip():
        errors["name"] = "Name is required."
    if not data.get("sheet_width", "").strip():
        errors["sheet_width"] = "Sheet width is required."
    else:
        try:
            float(data["sheet_width"])
        except (ValueError, TypeError):
            errors["sheet_width"] = "Enter a valid number in inches."
    if not data.get("sheet_height", "").strip():
        errors["sheet_height"] = "Sheet height is required."
    else:
        try:
            float(data["sheet_height"])
        except (ValueError, TypeError):
            errors["sheet_height"] = "Enter a valid number in inches."
    return errors


def _template_from_post(data):
    """Extract and convert form POST data to model field values (pts)."""

    def _fld(key):
        return _in_to_pts(data.get(key, ""))

    try:
        columns = max(1, int(data.get("columns", 1)))
    except (ValueError, TypeError):
        columns = 1
    try:
        rows = max(1, int(data.get("rows", 1)))
    except (ValueError, TypeError):
        rows = 1

    def _int_or_none(key):
        val = data.get(key, "").strip()
        return int(val) if val else None

    return {
        "name": data.get("name", "").strip(),
        "product_category_id": _int_or_none("product_category"),
        "cut_size_id": _int_or_none("cut_size"),
        "sheet_size_id": _int_or_none("sheet_size"),
        "cut_width": _fld("cut_width"),
        "cut_height": _fld("cut_height"),
        "sheet_width": _fld("sheet_width"),
        "sheet_height": _fld("sheet_height"),
        "bleed": _fld("bleed") or 0,
        # Margins are always 0 — layout is auto-centred on the sheet
        "margin_top": 0,
        "margin_right": 0,
        "margin_bottom": 0,
        "margin_left": 0,
        "columns": columns,
        "rows": rows,
        "barcode_x": _fld("barcode_x"),
        "barcode_y": _fld("barcode_y"),
        "barcode_width": _fld("barcode_width") or 90.0,  # 1.25" default
        "barcode_height": _fld("barcode_height") or 25.2,  # 0.35" default
        "print_barcode": data.get("print_barcode") == "on",
        "allow_mailmerge": data.get("allow_mailmerge") == "on",
        "cutter_program_id": int(data.get("cutter_program"))
        if data.get("cutter_program", "").strip()
        else None,
        "routing_preset_id": int(data.get("routing_preset"))
        if data.get("routing_preset", "").strip()
        else None,
        "notes": data.get("notes", "").strip(),
    }


def _build_preview_svg(data: dict) -> str:
    """
    Build a to-scale SVG preview of the imposition layout.

    *data* is a dict of form values (all in inches as strings).
    The grid is automatically centred on the sheet — no explicit margins.
    Returns an SVG string.
    """

    def _f(key, default=0.0):
        try:
            return float(data.get(key) or default)
        except (ValueError, TypeError):
            return float(default)

    sheet_w = _f("sheet_width")
    sheet_h = _f("sheet_height")
    bleed = _f("bleed")
    cols = max(1, int(_f("columns", 1)))
    rows = max(1, int(_f("rows", 1)))
    cut_w = _f("cut_width")
    cut_h = _f("cut_height")
    barcode_x = _f("barcode_x", -1)
    barcode_y = _f("barcode_y", -1)
    barcode_w_in = _f("barcode_width", 1.25)  # DC-646 default: 1.25"
    barcode_h_in = _f("barcode_height", 0.35)  # DC-646 default: 0.35"
    has_barcode = bool(data.get("barcode_x") and data.get("barcode_y"))

    if sheet_w <= 0 or sheet_h <= 0:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60"><text x="10" y="30" fill="#999" font-size="14">Enter sheet dimensions to preview.</text></svg>'

    # Scale to fit in 560px wide canvas
    max_canvas_w = 560.0
    max_canvas_h = 420.0
    scale = min(max_canvas_w / sheet_w, max_canvas_h / sheet_h)
    svg_w = sheet_w * scale
    svg_h = sheet_h * scale

    # Cell size = cut size + bleed on all sides
    cell_w = cut_w + 2 * bleed if cut_w > 0 else sheet_w / cols
    cell_h = cut_h + 2 * bleed if cut_h > 0 else sheet_h / rows

    # Auto-centre the grid on the sheet
    grid_w = cols * cell_w
    grid_h = rows * cell_h
    offset_x = (sheet_w - grid_w) / 2
    offset_y = (sheet_h - grid_h) / 2

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w:.1f}" height="{svg_h:.1f}" viewBox="0 0 {svg_w:.1f} {svg_h:.1f}">',
        # Sheet background
        f'<rect width="{svg_w:.1f}" height="{svg_h:.1f}" fill="#f9fafb" stroke="#d1d5db" stroke-width="1.5"/>',
    ]

    # Draw cells
    for r in range(rows):
        for c in range(cols):
            cx = offset_x + c * cell_w
            cy = offset_y + r * cell_h
            # Cell outer (including bleed)
            cell_x = cx * scale
            cell_y = cy * scale
            cell_sw = cell_w * scale
            cell_sh = cell_h * scale
            lines.append(
                f'<rect x="{cell_x:.2f}" y="{cell_y:.2f}" width="{cell_sw:.2f}" height="{cell_sh:.2f}" fill="none" stroke="#e5e7eb" stroke-width="0.6"/>'
            )
            # Trim area (inside bleed)
            trim_x = (cx + bleed) * scale
            trim_y = (cy + bleed) * scale
            trim_w = max(0, (cell_w - 2 * bleed) * scale)
            trim_h = max(0, (cell_h - 2 * bleed) * scale)
            lines.append(
                f'<rect x="{trim_x:.2f}" y="{trim_y:.2f}" width="{trim_w:.2f}" height="{trim_h:.2f}" fill="#dbeafe" fill-opacity="0.3" stroke="#3b82f6" stroke-width="1"/>'
            )
            # Cell label
            label_x = (cx + cell_w / 2) * scale
            label_y = (cy + cell_h / 2) * scale
            label = f"{c + 1},{r + 1}"
            lines.append(
                f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="{max(6, min(11, cell_w * scale / 4)):.0f}" fill="#6b7280">{label}</text>'
            )

    # Draw barcode marker if position is set
    # DC-646 Code 39 specs: configurable width × height (default 1.25" × 0.35")
    # Detect barcode overlap with any cell's trim area.
    # barcode_y is from the bottom of the sheet (PDF convention); convert to
    # "from top" for consistent comparison with SVG/grid coordinates.
    barcode_overlaps_trim = False
    if has_barcode and barcode_x >= 0 and barcode_y >= 0:
        bc_left = barcode_x
        bc_right = barcode_x + barcode_w_in
        bc_top = sheet_h - barcode_y - barcode_h_in   # from top of sheet
        bc_bottom = sheet_h - barcode_y               # from top of sheet
        for r in range(rows):
            for c in range(cols):
                cx = offset_x + c * cell_w
                cy = offset_y + r * cell_h
                trim_left = cx + bleed
                trim_right = cx + cell_w - bleed
                trim_top = cy + bleed
                trim_bottom = cy + cell_h - bleed
                if (bc_right > trim_left and bc_left < trim_right
                        and bc_bottom > trim_top and bc_top < trim_bottom):
                    barcode_overlaps_trim = True
                    break
            if barcode_overlaps_trim:
                break

    if has_barcode and barcode_x >= 0 and barcode_y >= 0:
        bx = barcode_x * scale
        # SVG Y axis is top-down; barcode_y is from bottom of sheet
        by = (sheet_h - barcode_y - barcode_h_in) * scale
        bw = barcode_w_in * scale
        bh = barcode_h_in * scale
        fill_color = "#ef4444" if barcode_overlaps_trim else "#f97316"
        stroke_color = "#dc2626" if barcode_overlaps_trim else "#ea580c"
        lines.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{fill_color}" fill-opacity="0.8" stroke="{stroke_color}" stroke-width="1"/>'
        )
        # Vertical bars to suggest Code 39 pattern
        num_bars = 9
        if num_bars > 0 and bw > 0:
            bar_gap = bw / (num_bars * 2 - 1)
            for i in range(num_bars):
                bar_x = bx + i * bar_gap * 2
                bar_w = bar_gap if i % 3 else bar_gap * 1.5
                lines.append(
                    f'<rect x="{bar_x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{stroke_color}" fill-opacity="0.5"/>'
                )
        lines.append(
            f'<text x="{bx + bw / 2:.1f}" y="{by - 3:.1f}" text-anchor="middle" font-size="8" fill="{stroke_color}">Code 39 (DC-646)</text>'
        )

    # Dimension labels
    lines.append(
        f'<text x="{svg_w / 2:.1f}" y="{svg_h - 4:.1f}" text-anchor="middle" font-size="9" fill="#6b7280">{sheet_w:g}" wide</text>'
    )
    lines.append(
        f'<text x="4" y="{svg_h / 2:.1f}" text-anchor="middle" font-size="9" fill="#6b7280" transform="rotate(-90 4 {svg_h / 2:.1f})">{sheet_h:g}" tall</text>'
    )

    lines.append("</svg>")
    svg = "\n".join(lines)

    if barcode_overlaps_trim:
        warning = (
            '<div style="margin-top:6px;padding:5px 8px;background:#fef2f2;border:1px solid #fca5a5;'
            'border-radius:4px;font-size:11px;color:#b91c1c;line-height:1.4;">'
            '&#9888; Barcode overlaps the trim area. Artwork may be obscured. '
            'You can still save — uncheck <em>Print barcode</em> if this is intentional.'
            '</div>'
        )
        return f'<div>{svg}{warning}</div>'

    return svg


class TemplateListView(ListView):
    model = ImpositionTemplate
    template_name = "impose/template_list.html"
    context_object_name = "templates"

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related(
                "product_category", "cut_size", "sheet_size", "routing_preset"
            )
        )
        # Filter by product_category FK
        cat_id = self.request.GET.get("product_category", "").strip()
        if cat_id:
            try:
                qs = qs.filter(product_category_id=int(cat_id))
            except (ValueError, TypeError):
                pass
        return qs

    def get_context_data(self, **kwargs):
        from .models import ProductCategory

        ctx = super().get_context_data(**kwargs)
        # All product categories that have at least one template
        ctx["product_categories"] = ProductCategory.objects.all().order_by("name")
        ctx["current_product_category"] = self.request.GET.get("product_category", "")
        return ctx


class TemplateCreateView(View):
    template_name = "impose/template_form.html"

    def get(self, request):
        ctx = _build_form_context()
        ctx["values"] = _get_initial_form_values()
        ctx["preview_svg"] = _build_preview_svg(_get_initial_form_values())
        return render(request, self.template_name, ctx)

    def post(self, request):
        data = request.POST

        # HTMX live preview request — return only the SVG fragment
        if request.headers.get("HX-Request") and request.POST.get("_preview"):
            return HttpResponse(
                _build_preview_svg(dict(data)), content_type="text/html"
            )

        errors = _validate_template_form(data)

        if not errors:
            fields = _template_from_post(data)
            tmpl = ImpositionTemplate.objects.create(**fields)
            messages.success(request, f"Template '{tmpl.name}' created.")
            return redirect("impose:list")

        ctx = _build_form_context()
        ctx["values"] = dict(data)
        ctx["errors"] = errors
        ctx["preview_svg"] = _build_preview_svg(dict(data))
        return render(request, self.template_name, ctx, status=400)


class TemplateEditView(View):
    template_name = "impose/template_form.html"

    def get(self, request, pk):
        tmpl = get_object_or_404(ImpositionTemplate, pk=pk)
        ctx = _build_form_context()
        ctx["template"] = tmpl
        ctx["values"] = _get_initial_form_values(tmpl)
        ctx["preview_svg"] = _build_preview_svg(_get_initial_form_values(tmpl))
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        tmpl = get_object_or_404(ImpositionTemplate, pk=pk)
        data = request.POST

        # HTMX live preview request — return only the SVG fragment
        if request.headers.get("HX-Request") and request.POST.get("_preview"):
            return HttpResponse(
                _build_preview_svg(dict(data)), content_type="text/html"
            )

        errors = _validate_template_form(data)

        if not errors:
            fields = _template_from_post(data)
            for key, val in fields.items():
                setattr(tmpl, key, val)
            tmpl.save()
            messages.success(request, f"Template '{tmpl.name}' updated.")
            return redirect("impose:list")

        ctx = _build_form_context()
        ctx["template"] = tmpl
        ctx["values"] = dict(data)
        ctx["errors"] = errors
        ctx["preview_svg"] = _build_preview_svg(dict(data))
        return render(request, self.template_name, ctx, status=400)


class TemplateDeleteView(DeleteView):
    model = ImpositionTemplate
    template_name = "impose/template_confirm_delete.html"
    success_url = reverse_lazy("impose:list")

    def form_valid(self, form):
        tmpl = self.get_object()
        messages.success(self.request, f"Template '{tmpl.name}' deleted.")
        return super().form_valid(form)


# ── Export ────────────────────────────────────────────────────────────────────


class TemplateExportView(View):
    """GET  /impose/<pk>/export/  → single-template JSON download."""

    def get(self, request, pk):
        tmpl = get_object_or_404(ImpositionTemplate, pk=pk)
        payload = {
            "version": EXPORT_VERSION,
            "templates": [_template_to_dict(tmpl)],
        }
        resp = HttpResponse(
            json.dumps(payload, indent=2),
            content_type="application/json",
        )
        safe_name = tmpl.name.replace(" ", "_").replace("/", "-")
        resp["Content-Disposition"] = f'attachment; filename="{safe_name}.json"'
        return resp


class TemplateExportAllView(View):
    """GET  /impose/export-all/  → all templates in one JSON download."""

    def get(self, request):
        templates = ImpositionTemplate.objects.all().order_by("name")
        payload = {
            "version": EXPORT_VERSION,
            "templates": [_template_to_dict(t) for t in templates],
        }
        resp = HttpResponse(
            json.dumps(payload, indent=2),
            content_type="application/json",
        )
        resp["Content-Disposition"] = 'attachment; filename="imposition_templates.json"'
        return resp


# ── Import ────────────────────────────────────────────────────────────────────


class TemplateImportView(View):
    """POST /impose/import/  → upload a JSON file and create/update templates."""

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            messages.error(request, "No file selected.")
            return redirect("impose:list")

        overwrite = request.POST.get("overwrite") == "on"

        try:
            payload = json.loads(upload.read())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            messages.error(request, f"Invalid JSON file: {exc}")
            return redirect("impose:list")

        entries = payload if isinstance(payload, list) else payload.get("templates", [])
        if not entries:
            messages.error(request, "No templates found in the uploaded file.")
            return redirect("impose:list")

        created = updated = skipped = errors = 0
        for d in entries:
            name = (d.get("name") or "").strip()
            if not name:
                errors += 1
                continue
            try:
                fields = _dict_to_template_fields(d)
            except Exception as exc:
                messages.warning(request, f"Skipped '{name}': {exc}")
                errors += 1
                continue

            existing = ImpositionTemplate.objects.filter(name=name).first()
            if existing:
                if overwrite:
                    for k, v in fields.items():
                        setattr(existing, k, v)
                    existing.save()
                    updated += 1
                else:
                    skipped += 1
            else:
                ImpositionTemplate.objects.create(**fields)
                created += 1

        parts = []
        if created:
            parts.append(f"{created} created")
        if updated:
            parts.append(f"{updated} updated")
        if skipped:
            parts.append(
                f"{skipped} skipped (already exist; enable overwrite to replace)"
            )
        if errors:
            parts.append(f"{errors} invalid entries ignored")
        messages.success(request, "Import complete: " + ", ".join(parts) + ".")
        return redirect("impose:list")


class PresetsView(View):
    template_name = "impose/presets.html"

    def get(self, request):
        from django.urls import reverse

        from apps.routing.models import RoutingPreset

        presets = RoutingPreset.objects.order_by("name")
        return render(
            request,
            self.template_name,
            {
                "presets": presets,
                "presets_tab_url": reverse("impose:presets"),
            },
        )
