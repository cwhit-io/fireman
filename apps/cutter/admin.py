from django.contrib import admin

from core.admin_mixins import ImportExportAdminMixin

from .models import CutterProgram

_PT = 72.0  # points per inch


def _pts_to_in(val):
    return round(float(val) / _PT, 6) if val is not None else None


def _in_to_pts(val, default=None):
    return round(float(val) * _PT, 3) if val is not None else default


@admin.register(CutterProgram)
class CutterProgramAdmin(ImportExportAdminMixin, admin.ModelAdmin):
    list_display = [
        "name",
        "duplo_code",
        "active",
        "barcode_x",
        "barcode_y",
        "barcode_width",
        "barcode_height",
    ]
    list_filter = ["active"]
    search_fields = ["name", "duplo_code"]
    fieldsets = [
        (None, {"fields": ["name", "duplo_code", "description", "active"]}),
        (
            "Barcode placement",
            {"fields": ["barcode_x", "barcode_y", "barcode_width", "barcode_height"]},
        ),
    ]
    import_label = "Cutter Programs"
    export_filename = "cutter_programs.json"
    export_key = "cutter_programs"

    def obj_to_dict(self, obj):
        return {
            "name": obj.name,
            "duplo_code": obj.duplo_code,
            "description": obj.description,
            "active": obj.active,
            "barcode_x": _pts_to_in(obj.barcode_x),
            "barcode_y": _pts_to_in(obj.barcode_y),
            "barcode_width": _pts_to_in(obj.barcode_width),
            "barcode_height": _pts_to_in(obj.barcode_height),
        }

    def dict_to_obj(self, d, overwrite):
        name = (d.get("name") or "").strip()
        if not name:
            return ("error", "Skipped entry with missing name.")
        fields = {
            "duplo_code": d.get("duplo_code", ""),
            "description": d.get("description", ""),
            "active": bool(d.get("active", True)),
            "barcode_x": _in_to_pts(d.get("barcode_x")),
            "barcode_y": _in_to_pts(d.get("barcode_y")),
            "barcode_width": _in_to_pts(d.get("barcode_width"), default=90.0),
            "barcode_height": _in_to_pts(d.get("barcode_height"), default=25.2),
        }
        existing = CutterProgram.objects.filter(name=name).first()
        if existing:
            if overwrite:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                return ("updated", None)
            return ("skipped", None)
        CutterProgram.objects.create(name=name, **fields)
        return ("created", None)
