from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView

from .models import POINTS_PER_INCH, ImpositionTemplate


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
    return {
        "layout_types": ImpositionTemplate.LayoutType.choices,
    }


def _get_initial_form_values(tmpl=None):
    if tmpl:
        return {
            "name": tmpl.name,
            "layout_type": tmpl.layout_type,
            "cut_width": _pts_to_in(tmpl.cut_width)
            if tmpl.cut_width is not None
            else "",
            "cut_height": _pts_to_in(tmpl.cut_height)
            if tmpl.cut_height is not None
            else "",
            "sheet_width": _pts_to_in(tmpl.sheet_width),
            "sheet_height": _pts_to_in(tmpl.sheet_height),
            "bleed": _pts_to_in(tmpl.bleed),
            "margin_top": _pts_to_in(tmpl.margin_top),
            "margin_right": _pts_to_in(tmpl.margin_right),
            "margin_bottom": _pts_to_in(tmpl.margin_bottom),
            "margin_left": _pts_to_in(tmpl.margin_left),
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
            "notes": tmpl.notes,
        }
    return {
        "name": "",
        "layout_type": "custom",
        "cut_width": "",
        "cut_height": "",
        "sheet_width": "",
        "sheet_height": "",
        "bleed": "0.125",
        "margin_top": "0.25",
        "margin_right": "0.25",
        "margin_bottom": "0.25",
        "margin_left": "0.25",
        "columns": "1",
        "rows": "1",
        "barcode_x": "",
        "barcode_y": "",
        "barcode_width": "1.25",   # DC-646 default: 1.25" wide (3-digit Code 39)
        "barcode_height": "0.35",  # DC-646 default: 0.35" tall
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

    return {
        "name": data.get("name", "").strip(),
        "layout_type": data.get("layout_type", "custom") or "custom",
        "cut_width": _fld("cut_width"),
        "cut_height": _fld("cut_height"),
        "sheet_width": _fld("sheet_width"),
        "sheet_height": _fld("sheet_height"),
        "bleed": _fld("bleed") or 0,
        "margin_top": _fld("margin_top") or 0,
        "margin_right": _fld("margin_right") or 0,
        "margin_bottom": _fld("margin_bottom") or 0,
        "margin_left": _fld("margin_left") or 0,
        "columns": columns,
        "rows": rows,
        "barcode_x": _fld("barcode_x"),
        "barcode_y": _fld("barcode_y"),
        "barcode_width": _fld("barcode_width") or 90.0,    # 1.25" default
        "barcode_height": _fld("barcode_height") or 25.2,  # 0.35" default
        "notes": data.get("notes", "").strip(),
    }


def _build_preview_svg(data: dict) -> str:
    """
    Build a to-scale SVG preview of the imposition layout.

    *data* is a dict of form values (all in inches as strings).
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
    margin_top = _f("margin_top")
    margin_right = _f("margin_right")
    margin_bottom = _f("margin_bottom")
    margin_left = _f("margin_left")
    cols = max(1, int(_f("columns", 1)))
    rows = max(1, int(_f("rows", 1)))
    barcode_x = _f("barcode_x", -1)
    barcode_y = _f("barcode_y", -1)
    barcode_w_in = _f("barcode_width", 1.25)   # DC-646 default: 1.25"
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

    printable_w = sheet_w - margin_left - margin_right
    printable_h = sheet_h - margin_top - margin_bottom
    cell_w = printable_w / cols if cols > 0 else 0
    cell_h = printable_h / rows if rows > 0 else 0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w:.1f}" height="{svg_h:.1f}" viewBox="0 0 {svg_w:.1f} {svg_h:.1f}">',
        # Sheet background
        f'<rect width="{svg_w:.1f}" height="{svg_h:.1f}" fill="#f9fafb" stroke="#d1d5db" stroke-width="1.5"/>',
        # Margin area (printable zone)
        f'<rect x="{margin_left * scale:.2f}" y="{margin_top * scale:.2f}" width="{printable_w * scale:.2f}" height="{printable_h * scale:.2f}" fill="none" stroke="#93c5fd" stroke-width="0.8" stroke-dasharray="4,2"/>',
    ]

    # Draw cells
    for r in range(rows):
        for c in range(cols):
            cx = margin_left + c * cell_w
            cy = margin_top + r * cell_h
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
    if has_barcode and barcode_x >= 0 and barcode_y >= 0:
        bx = barcode_x * scale
        # SVG Y axis is top-down; barcode_y is from bottom of sheet
        by = (sheet_h - barcode_y - barcode_h_in) * scale
        bw = barcode_w_in * scale
        bh = barcode_h_in * scale
        lines.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="#f97316" fill-opacity="0.8" stroke="#ea580c" stroke-width="1"/>'
        )
        # Vertical bars to suggest Code 39 pattern
        num_bars = 9
        if num_bars > 0 and bw > 0:
            bar_gap = bw / (num_bars * 2 - 1)
            for i in range(num_bars):
                bar_x = bx + i * bar_gap * 2
                bar_w = bar_gap if i % 3 else bar_gap * 1.5
                lines.append(
                    f'<rect x="{bar_x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="#ea580c" fill-opacity="0.5"/>'
                )
        lines.append(
            f'<text x="{bx + bw / 2:.1f}" y="{by - 3:.1f}" text-anchor="middle" font-size="8" fill="#ea580c">Code 39 (DC-646)</text>'
        )

    # Dimension labels
    lines.append(
        f'<text x="{svg_w / 2:.1f}" y="{svg_h - 4:.1f}" text-anchor="middle" font-size="9" fill="#6b7280">{sheet_w:g}" wide</text>'
    )
    lines.append(
        f'<text x="4" y="{svg_h / 2:.1f}" text-anchor="middle" font-size="9" fill="#6b7280" transform="rotate(-90 4 {svg_h / 2:.1f})">{sheet_h:g}" tall</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


class TemplateListView(ListView):
    model = ImpositionTemplate
    template_name = "impose/template_list.html"
    context_object_name = "templates"


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
