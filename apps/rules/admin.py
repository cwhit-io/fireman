from django.contrib import admin

from .models import Rule


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "priority",
        "condition_type",
        "condition_value",
        "imposition_template",
        "cutter_program",
        "routing_preset",
        "active",
    ]
    list_filter = ["active", "condition_type"]
    search_fields = ["name", "condition_value"]
    ordering = ["priority", "name"]
