from django.contrib import admin

from .models import Rule


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ["name", "priority", "condition_type", "condition_value", "action_type", "action_value", "active"]
    list_filter = ["active", "condition_type", "action_type"]
    search_fields = ["name", "condition_value"]
    ordering = ["priority", "name"]
