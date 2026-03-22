from django.contrib import admin

from core.admin_mixins import ImportExportAdminMixin

from .models import RoutingPreset


@admin.register(RoutingPreset)
class RoutingPresetAdmin(ImportExportAdminMixin, admin.ModelAdmin):
    list_display = ["name", "printer_queue", "duplex", "color_mode", "copies", "active"]
    list_filter = ["duplex", "color_mode", "active"]
    search_fields = ["name", "printer_queue"]
    import_label = "Routing Presets"
    export_filename = "routing_presets.json"
    export_key = "routing_presets"

    def obj_to_dict(self, obj):
        return {
            "name": obj.name,
            "printer_queue": obj.printer_queue,
            "media_type": obj.media_type,
            "media_size": obj.media_size,
            "duplex": obj.duplex,
            "color_mode": obj.color_mode,
            "tray": obj.tray,
            "copies": obj.copies,
            "fiery_options": obj.fiery_options,
            "extra_lpr_options": obj.extra_lpr_options,
            "active": obj.active,
        }

    def dict_to_obj(self, d, overwrite):
        name = (d.get("name") or "").strip()
        if not name:
            return ("error", "Skipped entry with missing name.")
        fields = {
            "printer_queue": d.get("printer_queue", "fiery"),
            "media_type": d.get("media_type", ""),
            "media_size": d.get("media_size", ""),
            "duplex": d.get("duplex", RoutingPreset.DuplexMode.SIMPLEX),
            "color_mode": d.get("color_mode", RoutingPreset.ColorMode.COLOR),
            "tray": d.get("tray", ""),
            "copies": int(d.get("copies") or 1),
            "fiery_options": d.get("fiery_options") or {},
            "extra_lpr_options": d.get("extra_lpr_options", ""),
            "active": bool(d.get("active", True)),
        }
        existing = RoutingPreset.objects.filter(name=name).first()
        if existing:
            if overwrite:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                return ("updated", None)
            return ("skipped", None)
        RoutingPreset.objects.create(name=name, **fields)
        return ("created", None)
