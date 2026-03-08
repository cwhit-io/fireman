from django.contrib import admin

from .models import ImpositionTemplate


@admin.register(ImpositionTemplate)
class ImpositionTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "layout_type",
        "columns",
        "rows",
        "sheet_width",
        "sheet_height",
    ]
    list_filter = ["layout_type"]
    search_fields = ["name"]
