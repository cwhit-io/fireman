from django.contrib import admin

from .models import BrandAsset, BrandAssetCategory, BrandColor


@admin.register(BrandAssetCategory)
class BrandAssetCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    ordering = ("order", "name")


@admin.register(BrandAsset)
class BrandAssetAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "order", "created_at")
    list_filter = ("category",)
    search_fields = ("name", "description")
    ordering = ("order", "name")
    fieldsets = (
        (None, {
            "fields": ("name", "category", "description", "svg_file", "order"),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Ensure only SVG files are accepted at the model level
        if obj.svg_file and not obj.svg_file.name.lower().endswith(".svg"):
            from django.core.exceptions import ValidationError
            self.message_user(request, "Only SVG files are accepted.", level="error")
            return
        super().save_model(request, obj, form, change)


@admin.register(BrandColor)
class BrandColorAdmin(admin.ModelAdmin):
    list_display = ("name", "hex_value", "cmyk_label", "pantone_label", "order")
    ordering = ("order", "name")
    fieldsets = (
        (None, {
            "fields": ("name", "hex_value", "order"),
        }),
        ("Additional Color Values", {
            "fields": ("rgb_label", "cmyk_label", "pantone_label"),
            "classes": ("collapse",),
        }),
    )
