from django.contrib import admin

from .models import RoutingPreset


@admin.register(RoutingPreset)
class RoutingPresetAdmin(admin.ModelAdmin):
    list_display = ["name", "printer_queue", "duplex", "color_mode", "copies", "active"]
    list_filter = ["duplex", "color_mode", "active"]
    search_fields = ["name", "printer_queue"]
