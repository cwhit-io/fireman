from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView

from .models import RoutingPreset


def _build_form_context():
    return {
        "duplex_modes": RoutingPreset.DuplexMode.choices,
        "color_modes": RoutingPreset.ColorMode.choices,
    }


def _get_initial_form_values(preset=None):
    if preset:
        return {
            "name": preset.name,
            "printer_queue": preset.printer_queue,
            "media_type": preset.media_type,
            "media_size": preset.media_size,
            "duplex": preset.duplex,
            "color_mode": preset.color_mode,
            "tray": preset.tray,
            "copies": str(preset.copies),
            "extra_lpr_options": preset.extra_lpr_options,
            "active": "on" if preset.active else "",
        }
    return {
        "name": "",
        "printer_queue": "fiery",
        "media_type": "",
        "media_size": "",
        "duplex": RoutingPreset.DuplexMode.SIMPLEX,
        "color_mode": RoutingPreset.ColorMode.COLOR,
        "tray": "",
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

        if not errors:
            try:
                copies = max(1, int(data.get("copies", 1)))
            except (ValueError, TypeError):
                copies = 1

            preset = RoutingPreset.objects.create(
                name=data["name"].strip(),
                printer_queue=data["printer_queue"].strip(),
                media_type=data.get("media_type", "").strip(),
                media_size=data.get("media_size", "").strip(),
                duplex=data.get("duplex", RoutingPreset.DuplexMode.SIMPLEX),
                color_mode=data.get("color_mode", RoutingPreset.ColorMode.COLOR),
                tray=data.get("tray", "").strip(),
                copies=copies,
                extra_lpr_options=data.get("extra_lpr_options", "").strip(),
                active=data.get("active") == "on",
            )
            messages.success(request, f"Printer preset '{preset.name}' created.")
            return redirect("routing:list")

        ctx = _build_form_context()
        ctx["values"] = dict(data)
        ctx["errors"] = errors
        return render(request, self.template_name, ctx, status=400)


class PresetEditView(View):
    template_name = "routing/preset_form.html"

    def get(self, request, pk):
        preset = get_object_or_404(RoutingPreset, pk=pk)
        ctx = _build_form_context()
        ctx["preset"] = preset
        ctx["values"] = _get_initial_form_values(preset)
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        preset = get_object_or_404(RoutingPreset, pk=pk)
        data = request.POST
        errors = _validate_preset_form(data)

        if not errors:
            preset.name = data["name"].strip()
            preset.printer_queue = data["printer_queue"].strip()
            preset.media_type = data.get("media_type", "").strip()
            preset.media_size = data.get("media_size", "").strip()
            preset.duplex = data.get("duplex", RoutingPreset.DuplexMode.SIMPLEX)
            preset.color_mode = data.get("color_mode", RoutingPreset.ColorMode.COLOR)
            preset.tray = data.get("tray", "").strip()
            try:
                preset.copies = max(1, int(data.get("copies", 1)))
            except (ValueError, TypeError):
                preset.copies = 1
            preset.extra_lpr_options = data.get("extra_lpr_options", "").strip()
            preset.active = data.get("active") == "on"
            preset.save()
            messages.success(request, f"Printer preset '{preset.name}' updated.")
            return redirect("routing:list")

        ctx = _build_form_context()
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
