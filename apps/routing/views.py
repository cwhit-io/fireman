from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView

from .fiery_options import build_fiery_sections
from .models import RoutingPreset


def _extract_fiery_options(post_data) -> dict:
    """Collect all fiery_<KEY>=<value> POST fields into a plain dict."""
    opts = {}
    for key, value in post_data.items():
        if key.startswith("fiery_"):
            opt_key = key[6:]
            v = value.strip() if isinstance(value, str) else value
            if v:
                opts[opt_key] = v
    return opts


def _build_form_context(fiery_options=None):
    return {
        "fiery_sections": build_fiery_sections(fiery_options or {}),
    }


def _get_initial_form_values(preset=None):
    if preset:
        return {
            "name": preset.name,
            "printer_queue": preset.printer_queue,
            "copies": str(preset.copies),
            "extra_lpr_options": preset.extra_lpr_options,
            "active": "on" if preset.active else "",
        }
    return {
        "name": "",
        "printer_queue": "fiery_hold",
        "copies": "1",
        "extra_lpr_options": "",
        "active": "on",
    }


def _validate_preset_form(data):
    errors = {}
    if not data.get("name", "").strip():
        errors["name"] = "Name is required."
    if not data.get("printer_queue", "").strip():
        errors["printer_queue"] = "Printer queue is required."
    return errors


class PresetListView(ListView):
    model = RoutingPreset
    template_name = "routing/preset_list.html"
    context_object_name = "presets"


class PresetCreateView(View):
    template_name = "routing/preset_form.html"

    def get(self, request):
        ctx = _build_form_context()
        ctx["values"] = _get_initial_form_values()
        return render(request, self.template_name, ctx)

    def post(self, request):
        data = request.POST
        errors = _validate_preset_form(data)
        fiery_options = _extract_fiery_options(data)

        if not errors:
            try:
                copies = max(1, int(data.get("copies", 1)))
            except (ValueError, TypeError):
                copies = 1

            preset = RoutingPreset.objects.create(
                name=data["name"].strip(),
                printer_queue=data["printer_queue"].strip(),
                copies=copies,
                fiery_options=fiery_options,
                extra_lpr_options=data.get("extra_lpr_options", "").strip(),
                active=data.get("active") == "on",
            )
            messages.success(request, f"Printer preset '{preset.name}' created.")
            return redirect("routing:list")

        ctx = _build_form_context(fiery_options)
        ctx["values"] = dict(data)
        ctx["errors"] = errors
        return render(request, self.template_name, ctx, status=400)


class PresetEditView(View):
    template_name = "routing/preset_form.html"

    def get(self, request, pk):
        preset = get_object_or_404(RoutingPreset, pk=pk)
        ctx = _build_form_context(preset.fiery_options)
        ctx["preset"] = preset
        ctx["values"] = _get_initial_form_values(preset)
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        preset = get_object_or_404(RoutingPreset, pk=pk)
        data = request.POST
        errors = _validate_preset_form(data)
        fiery_options = _extract_fiery_options(data)

        if not errors:
            preset.name = data["name"].strip()
            preset.printer_queue = data["printer_queue"].strip()
            preset.fiery_options = fiery_options
            preset.extra_lpr_options = data.get("extra_lpr_options", "").strip()
            try:
                preset.copies = max(1, int(data.get("copies", 1)))
            except (ValueError, TypeError):
                preset.copies = 1
            preset.active = data.get("active") == "on"
            preset.save()
            messages.success(request, f"Printer preset '{preset.name}' updated.")
            return redirect("routing:list")

        ctx = _build_form_context(fiery_options)
        ctx["preset"] = preset
        ctx["values"] = dict(data)
        ctx["errors"] = errors
        return render(request, self.template_name, ctx, status=400)


class PresetDeleteView(DeleteView):
    model = RoutingPreset
    template_name = "routing/preset_confirm_delete.html"
    success_url = reverse_lazy("routing:list")

    def form_valid(self, form):
        preset = self.get_object()
        messages.success(self.request, f"Printer preset '{preset.name}' deleted.")
        return super().form_valid(form)


class PresetTestConnectionView(View):
    """POST to this view to test connectivity to the preset's printer queue."""

    def post(self, request, pk):
        preset = get_object_or_404(RoutingPreset, pk=pk)
        from .services import test_printer_connection

        result = test_printer_connection(preset)
        return JsonResponse(result)
