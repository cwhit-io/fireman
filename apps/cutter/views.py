from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView

from .models import CutterProgram
from .services import get_barcode_tif_preview


def _get_initial_form_values(program=None):
    if program:
        return {
            "name": program.name,
            "duplo_code": program.duplo_code,
            "description": program.description,
            "active": "on" if program.active else "",
            "barcode_x": str(program.barcode_x)
            if program.barcode_x is not None
            else "",
            "barcode_y": str(program.barcode_y)
            if program.barcode_y is not None
            else "",
            "barcode_width": str(program.barcode_width),
            "barcode_height": str(program.barcode_height),
        }
    return {
        "name": "",
        "duplo_code": "",
        "description": "",
        "active": "on",
        "barcode_x": "",
        "barcode_y": "",
        "barcode_width": "90.0",
        "barcode_height": "25.2",
    }


def _validate_program_form(data):
    errors = {}
    if not data.get("name", "").strip():
        errors["name"] = "Name is required."
    if not data.get("duplo_code", "").strip():
        errors["duplo_code"] = "Duplo code is required."
    return errors


def _parse_optional_decimal(value: str):
    """Return a Decimal from a string, or None if blank/invalid."""
    from decimal import Decimal, InvalidOperation

    v = (value or "").strip()
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def _parse_decimal(value: str, default):
    """Return a Decimal from a string, falling back to default."""
    from decimal import Decimal, InvalidOperation

    v = (value or "").strip()
    try:
        return Decimal(v)
    except (InvalidOperation, TypeError):
        return Decimal(str(default))


class ProgramListView(ListView):
    model = CutterProgram
    template_name = "cutter/program_list.html"
    context_object_name = "programs"

    def get_queryset(self):
        sort = self.request.GET.get("sort", "duplo_code")
        if sort not in ("name", "-name", "duplo_code", "-duplo_code"):
            sort = "duplo_code"
        return CutterProgram.objects.order_by(sort)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sort"] = self.request.GET.get("sort", "duplo_code")
        return ctx


class ProgramCreateView(View):
    template_name = "cutter/program_form.html"

    def get(self, request):
        ctx = {"values": _get_initial_form_values()}
        return render(request, self.template_name, ctx)

    def post(self, request):
        data = request.POST
        errors = _validate_program_form(data)

        if not errors:
            program = CutterProgram.objects.create(
                name=data["name"].strip(),
                duplo_code=data["duplo_code"].strip(),
                description=data.get("description", "").strip(),
                active=data.get("active") == "on",
                barcode_x=_parse_optional_decimal(data.get("barcode_x", "")),
                barcode_y=_parse_optional_decimal(data.get("barcode_y", "")),
                barcode_width=_parse_decimal(data.get("barcode_width", ""), 90.0),
                barcode_height=_parse_decimal(data.get("barcode_height", ""), 25.2),
            )
            messages.success(request, f"Cutter program '{program.name}' created.")
            return redirect("cutter:list")

        ctx = {"values": dict(data), "errors": errors}
        return render(request, self.template_name, ctx, status=400)


class ProgramEditView(View):
    template_name = "cutter/program_form.html"

    def get(self, request, pk):
        program = get_object_or_404(CutterProgram, pk=pk)
        ctx = {"program": program, "values": _get_initial_form_values(program)}
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        program = get_object_or_404(CutterProgram, pk=pk)
        data = request.POST
        errors = _validate_program_form(data)

        if not errors:
            program.name = data["name"].strip()
            program.duplo_code = data["duplo_code"].strip()
            program.description = data.get("description", "").strip()
            program.active = data.get("active") == "on"
            program.barcode_x = _parse_optional_decimal(data.get("barcode_x", ""))
            program.barcode_y = _parse_optional_decimal(data.get("barcode_y", ""))
            program.barcode_width = _parse_decimal(data.get("barcode_width", ""), 90.0)
            program.barcode_height = _parse_decimal(
                data.get("barcode_height", ""), 25.2
            )
            program.save()
            messages.success(request, f"Cutter program '{program.name}' updated.")
            return redirect("cutter:list")

        ctx = {"program": program, "values": dict(data), "errors": errors}
        return render(request, self.template_name, ctx, status=400)


class ProgramDeleteView(DeleteView):
    model = CutterProgram
    template_name = "cutter/program_confirm_delete.html"
    success_url = reverse_lazy("cutter:list")

    def form_valid(self, form):
        program = self.get_object()
        messages.success(self.request, f"Cutter program '{program.name}' deleted.")
        return super().form_valid(form)


class ProgramBarcodeView(View):
    """Return the pre-generated barcode TIF as a PNG for a cutter program."""

    def get(self, request, pk):
        from django.http import Http404

        program = get_object_or_404(CutterProgram, pk=pk)
        png_bytes = get_barcode_tif_preview(program.duplo_code)
        if png_bytes is None:
            raise Http404("No barcode TIF found for this program.")
        return HttpResponse(png_bytes, content_type="image/png")
