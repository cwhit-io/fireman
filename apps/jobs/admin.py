from django.contrib import admin
from django.shortcuts import render
from django.utils.html import format_html

from .models import PrintJob

_STATUS_COLORS = {
    PrintJob.Status.ERROR: "#dc2626",
    PrintJob.Status.SENT: "#16a34a",
    PrintJob.Status.IMPOSED: "#2563eb",
    PrintJob.Status.PROCESSING: "#ea580c",
}

_COPY_BTN_STYLE = "font-size:11px;padding:1px 6px;cursor:pointer;"


def _copy_field(value):
    """Return format_html markup with a click-to-copy button for *value*."""
    return format_html(
        "<span>{val}</span>"
        '&nbsp;<button type="button" data-copy="{val}"'
        ' style="{style}">Copy</button>'
        "<script>(function(){{"
        "var b=document.currentScript.previousElementSibling;"
        'b.addEventListener("click",function(){{'
        "navigator.clipboard.writeText(b.dataset.copy)"
        '.then(function(){{b.textContent="Copied!";'
        'setTimeout(function(){{b.textContent="Copy";}},1500);}});'
        "}});}})()</script>",
        val=value,
        style=_COPY_BTN_STYLE,
    )


def _reprocess_and_reroute(modeladmin, request, queryset):
    """Bulk-change routing preset, reset to PENDING, and re-queue jobs."""
    from apps.jobs.tasks import process_job_task
    from apps.routing.models import RoutingPreset

    if "apply" in request.POST:
        preset_id = request.POST.get("routing_preset")
        try:
            preset = RoutingPreset.objects.get(pk=preset_id)
        except RoutingPreset.DoesNotExist:
            modeladmin.message_user(
                request, "Invalid routing preset selected.", level="error"
            )
            return None

        count = 0
        errors = 0
        for job in queryset:
            job.routing_preset = preset
            job.status = PrintJob.Status.PENDING
            job.save(update_fields=["routing_preset", "status"])
            try:
                process_job_task.delay(str(job.pk))
                count += 1
            except Exception:
                errors += 1
        if count:
            modeladmin.message_user(
                request,
                f'Reprocessing {count} job(s) with preset "{preset.name}".',
            )
        if errors:
            modeladmin.message_user(
                request,
                f"{errors} job(s) could not be queued (broker unavailable?).",
                level="warning",
            )
        return None

    presets = RoutingPreset.objects.filter(active=True).order_by("name")
    return render(
        request,
        "admin/jobs/printjob/reroute_action.html",
        {
            "queryset": queryset,
            "presets": presets,
            "opts": modeladmin.model._meta,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )


_reprocess_and_reroute.short_description = "Reprocess and Reroute Selected Jobs"


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "colored_status",
        "page_count",
        "page_size_label",
        "product_type",
        "created_at",
    ]
    list_filter = ["status", "product_type"]
    search_fields = ["name", "product_type"]
    readonly_fields = [
        "job_id_with_copy",
        "colored_status",
        "page_count",
        "page_width",
        "page_height",
        "page_size_label",
        "file_path_with_copy",
        "imposed_file_path_with_copy",
        "original_file_preview",
        "imposed_file_preview",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "created_at"
    actions = [_reprocess_and_reroute]

    @admin.display(description="Status", ordering="status")
    def colored_status(self, obj):
        color = _STATUS_COLORS.get(obj.status, "#6b7280")
        label = obj.get_status_display()
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:4px;font-size:11px;font-weight:bold;">{}</span>',
            color,
            label,
        )

    @admin.display(description="Job ID")
    def job_id_with_copy(self, obj):
        return _copy_field(str(obj.pk))

    @admin.display(description="File path")
    def file_path_with_copy(self, obj):
        if not obj.file:
            return "—"
        return _copy_field(obj.file.name)

    @admin.display(description="Imposed file path")
    def imposed_file_path_with_copy(self, obj):
        if not obj.imposed_file:
            return "—"
        return _copy_field(obj.imposed_file.name)

    @admin.display(description="Original PDF preview")
    def original_file_preview(self, obj):
        if not obj.file:
            return "—"
        try:
            url = obj.file.url
        except ValueError:
            return "—"
        return format_html(
            '<iframe src="{}" width="100%" height="500px"'
            ' style="border:1px solid #ccc;border-radius:4px;"></iframe>',
            url,
        )

    @admin.display(description="Imposed PDF preview")
    def imposed_file_preview(self, obj):
        if not obj.imposed_file:
            return "—"
        try:
            url = obj.imposed_file.url
        except ValueError:
            return "—"
        return format_html(
            '<iframe src="{}" width="100%" height="500px"'
            ' style="border:1px solid #ccc;border-radius:4px;"></iframe>',
            url,
        )
