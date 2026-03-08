from django.contrib import admin

from .models import ImpositionTemplate, PrintSize, ProductCategory


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "description"]
    search_fields = ["name"]


@admin.register(PrintSize)
class PrintSizeAdmin(admin.ModelAdmin):
    list_display = ["name", "size_type", "width", "height"]
    list_filter = ["size_type"]
    search_fields = ["name"]


@admin.register(ImpositionTemplate)
class ImpositionTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "product_category",
        "layout_type",
        "cut_size",
        "sheet_size",
        "columns",
        "rows",
    ]
    list_filter = ["layout_type", "product_category", "cut_size", "sheet_size"]
    search_fields = ["name"]
