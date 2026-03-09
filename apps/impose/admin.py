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


def _make_set_category_action(category):
    """Factory that creates a bulk-set-category admin action for a given category."""

    def action(modeladmin, request, queryset):
        updated = queryset.update(product_category=category)
        modeladmin.message_user(
            request,
            f"Set category to '{category.name}' for {updated} template(s).",
        )

    action.short_description = f"Set category → {category.name}"
    action.__name__ = f"set_category_{category.pk}"
    return action


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

    def get_actions(self, request):
        actions = super().get_actions(request)
        # Dynamically add one action per product category for bulk assignment
        for category in ProductCategory.objects.order_by("name"):
            action_fn = _make_set_category_action(category)
            actions[action_fn.__name__] = (
                action_fn,
                action_fn.__name__,
                action_fn.short_description,
            )
        return actions
