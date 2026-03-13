from django.contrib import admin

from .models import MailMergeJob


@admin.register(MailMergeJob)
class MailMergeJobAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "record_count", "created_at")
    list_filter = ("status",)
    readonly_fields = (
        "id",
        "status",
        "record_count",
        "error_message",
        "output_file",
        "created_at",
        "updated_at",
    )
    search_fields = ("name",)
