from django.contrib import admin

from .models import Rule


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "product_category",
        "cut_size",
        "sheet_size",
        "imposition_template",
        "cutter_program",
        "routing_preset",
        "active",
    ]
    list_filter = ["active", "product_category", "cut_size", "sheet_size"]
    search_fields = ["name"]
    ordering = ["name"]
