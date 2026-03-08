from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView

from .models import ImpositionTemplate


def _pts_to_in(pts):
    """Convert points to inches, rounded to 4 decimal places."""
    if pts is None:
        return ""
    return round(float(pts) / 72.0, 4)


def _in_to_pts(inches_str):
    """Convert inches string to points. Returns None if blank/invalid."""
    s = (inches_str or "").strip()
    if not s:
        return None
    try:
        return float(s) * 72.0
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
            "sheet_width": _pts_to_in(tmpl.sheet_width),
            "sheet_height": _pts_to_in(tmpl.sheet_height),
            "bleed": _pts_to_in(tmpl.bleed),
            "margin_top": _pts_to_in(tmpl.margin_top),
            "margin_right": _pts_to_in(tmpl.margin_right),
            "margin_bottom": _pts_to_in(tmpl.margin_bottom),
            "margin_left": _pts_to_in(tmpl.margin_left),
            "columns": str(tmpl.columns),
            "rows": str(tmpl.rows),
            "barcode_x": _pts_to_in(tmpl.barcode_x) if tmpl.barcode_x is not None else "",
            "barcode_y": _pts_to_in(tmpl.barcode_y) if tmpl.barcode_y is not None else "",
            "notes": tmpl.notes,
        }
    return {
        "name": "",
        "layout_type": "",
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
        "notes": "",
    }


def _validate_template_form(data):
    errors = {}
    if not data.get("name", "").strip():
        errors["name"] = "Name is required."
    if not data.get("layout_type", ""):
        errors["layout_type"] = "Layout type is required."
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
        "layout_type": data.get("layout_type", ""),
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
        "notes": data.get("notes", "").strip(),
    }


class TemplateListView(ListView):
    model = ImpositionTemplate
    template_name = "impose/template_list.html"
    context_object_name = "templates"


class TemplateCreateView(View):
    template_name = "impose/template_form.html"

    def get(self, request):
        ctx = _build_form_context()
        ctx["values"] = _get_initial_form_values()
        return render(request, self.template_name, ctx)

    def post(self, request):
        data = request.POST
        errors = _validate_template_form(data)

        if not errors:
            fields = _template_from_post(data)
            tmpl = ImpositionTemplate.objects.create(**fields)
            messages.success(request, f"Template '{tmpl.name}' created.")
            return redirect("impose:list")

        ctx = _build_form_context()
        ctx["values"] = dict(data)
        ctx["errors"] = errors
        return render(request, self.template_name, ctx, status=400)


class TemplateEditView(View):
    template_name = "impose/template_form.html"

    def get(self, request, pk):
        tmpl = get_object_or_404(ImpositionTemplate, pk=pk)
        ctx = _build_form_context()
        ctx["template"] = tmpl
        ctx["values"] = _get_initial_form_values(tmpl)
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        tmpl = get_object_or_404(ImpositionTemplate, pk=pk)
        data = request.POST
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
        return render(request, self.template_name, ctx, status=400)


class TemplateDeleteView(DeleteView):
    model = ImpositionTemplate
    template_name = "impose/template_confirm_delete.html"
    success_url = reverse_lazy("impose:list")

    def form_valid(self, form):
        tmpl = self.get_object()
        messages.success(self.request, f"Template '{tmpl.name}' deleted.")
        return super().form_valid(form)
