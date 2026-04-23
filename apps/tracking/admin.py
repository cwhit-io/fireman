from django.contrib import admin, messages
from django.db.models import Count, Sum, DecimalField
from django.db.models.functions import Coalesce
from django.utils.html import format_html

from .models import CostRate, PrintLog
from .services import sync_fiery_logs


# ── Cost Rates ────────────────────────────────────────────────────────────────

@admin.register(CostRate)
class CostRateAdmin(admin.ModelAdmin):
    list_display = ["label", "color_per_page", "bw_per_page", "active", "updated_at"]
    list_editable = ["active"]
    ordering = ["-updated_at"]


# ── Print Log ─────────────────────────────────────────────────────────────────

@admin.register(PrintLog)
class PrintLogAdmin(admin.ModelAdmin):
    list_display = [
        "printed_at", "username", "job_name_short", "color_pages", "bw_pages",
        "copies", "color_mode", "media_size", "calculated_cost_display",
    ]
    list_filter = ["color_mode", "duplex", "printed_at"]
    search_fields = ["username", "job_name", "fiery_job_id"]
    readonly_fields = [
        "fiery_job_id", "username", "job_name", "printed_at", "imported_at",
        "color_pages", "bw_pages", "copies", "color_mode",
        "media_size", "media_type", "duplex",
        "cost_rate", "calculated_cost", "raw_data",
    ]
    date_hierarchy = "printed_at"
    ordering = ["-printed_at"]
    actions = ["recalculate_costs"]

    change_list_template = "admin/tracking/printlog/change_list.html"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path("sync/", self.admin_site.admin_view(self.sync_view), name="tracking_sync"),
        ]
        return custom + urls

    def sync_view(self, request):
        from django.shortcuts import redirect
        result = sync_fiery_logs()
        if "error" in result:
            self.message_user(request, f"Sync failed: {result['error']}", messages.ERROR)
        else:
            self.message_user(
                request,
                f"Sync complete — {result.get('created', 0)} new, "
                f"{result.get('skipped', 0)} skipped, "
                f"{result.get('errors', 0)} errors.",
                messages.SUCCESS,
            )
        return redirect("..")

    def job_name_short(self, obj):
        return obj.job_name[:60] + "…" if len(obj.job_name) > 60 else obj.job_name
    job_name_short.short_description = "Job"

    def calculated_cost_display(self, obj):
        if obj.calculated_cost is None:
            return "—"
        return f"${obj.calculated_cost:.4f}"
    calculated_cost_display.short_description = "Cost"

    @admin.action(description="Recalculate costs using the active rate")
    def recalculate_costs(self, request, queryset):
        rate = CostRate.objects.filter(active=True).order_by("-updated_at").first()
        if not rate:
            self.message_user(request, "No active cost rate found.", messages.ERROR)
            return
        count = 0
        for log in queryset:
            log.calculate_cost(rate)
            count += 1
        self.message_user(request, f"Recalculated costs for {count} job(s).", messages.SUCCESS)

    def changelist_view(self, request, extra_context=None):
        # Aggregate usage by user for the summary table
        qs = self.get_queryset(request)

        user_totals = (
            qs.values("username")
            .annotate(
                total_color=Coalesce(Sum("color_pages"), 0),
                total_bw=Coalesce(Sum("bw_pages"), 0),
                total_jobs=Count("id"),
                total_cost=Coalesce(
                    Sum("calculated_cost"), 0, output_field=DecimalField()
                ),
            )
            .order_by("-total_color")
        )

        extra_context = extra_context or {}
        extra_context["user_totals"] = user_totals
        return super().changelist_view(request, extra_context=extra_context)
