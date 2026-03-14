from django.contrib import admin
from django.db import models as db_models
from django.forms import Textarea

from .models import AddressBlockConfig, MailMergeJob


@admin.register(MailMergeJob)
class MailMergeJobAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "status", "record_count", "created_at")
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


@admin.register(AddressBlockConfig)
class AddressBlockConfigAdmin(admin.ModelAdmin):
    """Singleton admin for the site-wide address block defaults."""

    fieldsets = (
        (
            "Address Position",
            {
                "fields": ("addr_x_in", "addr_y_in"),
                "description": (
                    "Inches from the card right / bottom edges. "
                    'Leave blank to use defaults (4.5" from right, 2.5" from bottom).'
                ),
            },
        ),
        (
            "Address Block Template",
            {
                "fields": ("address_template",),
                "description": (
                    "Each line prints top-to-bottom. Use {field_name} tokens for CSV "
                    "fields; plain text for static lines like 'Address Service Requested'. "
                    "Lines where every token is blank are skipped automatically. "
                    "{encodedimbno} renders as the visual IMb barcode at the barcode position."
                ),
            },
        ),
        (
            "Typography",
            {
                "fields": ("font_name", "font_size", "line_height"),
            },
        ),
        (
            "USPS IMb Barcode (encodedimbno)",
            {
                "fields": ("barcode_font_size", "barcode_x_in", "barcode_y_in"),
                "description": "Leave X/Y blank to use the main address block position.",
            },
        ),
        (
            "Presort Tray ID (presorttrayid)",
            {
                "fields": ("tray_font_size", "tray_x_in", "tray_y_in"),
                "description": "Leave X/Y blank to include tray ID in the normal address text flow.",
            },
        ),
        (
            "Preview Card Size",
            {
                "fields": (
                    "preview_card_width_in",
                    "preview_card_height_in",
                    "addr_block_width_in",
                ),
                "classes": ("collapse",),
                "description": "Used only for the old frontend preview — not required.",
            },
        ),
    )

    formfield_overrides = {
        db_models.TextField: {
            "widget": Textarea(
                attrs={"rows": 10, "cols": 60, "style": "font-family:monospace"}
            )
        },
    }

    def has_add_permission(self, request):
        # Singleton — only allow editing when a row already exists.
        return not AddressBlockConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redirect straight to the single edit page.
        obj = AddressBlockConfig.get_solo()
        from django.http import HttpResponseRedirect
        from django.urls import reverse

        return HttpResponseRedirect(
            reverse("admin:mailmerge_addressblockconfig_change", args=[obj.pk])
        )
