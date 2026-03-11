from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.jobs.models import PrintJob

from .models import ImpositionTemplate, PrintSize, ProductCategory


class RecentPrintJobInline(admin.TabularInline):
    """Shows up to 10 most-recent PrintJobs that used this template."""

    model = PrintJob
    fk_name = "imposition_template"
    fields = ["job_link", "colored_status", "created_at"]
    readonly_fields = ["job_link", "colored_status", "created_at"]
    extra = 0
    max_num = 0
    can_delete = False
    verbose_name = "Recent Job"
    verbose_name_plural = "Recent Jobs (last 10)"
    ordering = ["-created_at"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        parent_pk = request.resolver_match.kwargs.get("object_id")
        if parent_pk:
            recent_ids = list(
                PrintJob.objects.filter(imposition_template_id=parent_pk)
                .order_by("-created_at")
                .values_list("id", flat=True)[:10]
            )
            return qs.filter(pk__in=recent_ids).order_by("-created_at")
        return qs.none()

    @admin.display(description="Job")
    def job_link(self, obj):
        url = reverse("admin:jobs_printjob_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.name or str(obj.pk))

    @admin.display(description="Status")
    def colored_status(self, obj):
        color_map = {
            "error": "#dc2626",
            "sent": "#16a34a",
            "imposed": "#2563eb",
            "processing": "#ea580c",
        }
        color = color_map.get(obj.status, "#6b7280")
        label = obj.get_status_display()
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:bold;">{}</span>',
            color,
            label,
        )


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
    inlines = [RecentPrintJobInline]

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
