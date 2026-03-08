from django.contrib import admin

from .models import CutterProgram


@admin.register(CutterProgram)
class CutterProgramAdmin(admin.ModelAdmin):
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
