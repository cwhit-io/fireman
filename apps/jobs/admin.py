from django.contrib import admin

from .models import PrintJob


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "page_count", "page_size_label", "product_type", "created_at"]
    list_filter = ["status", "product_type"]
    search_fields = ["name", "product_type"]
    readonly_fields = ["id", "page_count", "page_width", "page_height", "page_size_label", "created_at", "updated_at"]
    date_hierarchy = "created_at"
