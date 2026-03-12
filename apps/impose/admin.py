import json

from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html

from apps.jobs.models import PrintJob

from .models import POINTS_PER_INCH, ImpositionTemplate, PrintSize, ProductCategory


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


# ── Shared JSON serialisation helpers (mirrors apps/impose/views.py) ──────────

_EXPORT_VERSION = 1

_PT_FIELDS = [
    "cut_width",
    "cut_height",
    "sheet_width",
    "sheet_height",
    "bleed",
    "margin_top",
    "margin_right",
    "margin_bottom",
    "margin_left",
    "barcode_x",
    "barcode_y",
    "barcode_width",
    "barcode_height",
]
_PLAIN_FIELDS = ["name", "columns", "rows", "notes", "print_barcode"]


def _tmpl_to_dict(tmpl):
    d = {f: getattr(tmpl, f) for f in _PLAIN_FIELDS}
    for f in _PT_FIELDS:
        val = getattr(tmpl, f)
        d[f] = round(float(val) / POINTS_PER_INCH, 6) if val is not None else None
    d["product_category"] = (
        tmpl.product_category.name if tmpl.product_category else None
    )
    return d


def _dict_to_fields(d):
    fields = {f: d.get(f) for f in _PLAIN_FIELDS}
    for f in _PT_FIELDS:
        val = d.get(f)
        fields[f] = round(float(val) * POINTS_PER_INCH, 3) if val is not None else None
    for f in ["bleed", "margin_top", "margin_right", "margin_bottom", "margin_left"]:
        if fields[f] is None:
            fields[f] = 0
    for f in ["barcode_width", "barcode_height"]:
        if fields[f] is None:
            fields[f] = 90.0 if f == "barcode_width" else 25.2
    if fields.get("print_barcode") is None:
        fields["print_barcode"] = True
    cat_name = d.get("product_category") or ""
    if cat_name:
        cat = ProductCategory.objects.filter(name=cat_name).first()
        fields["product_category_id"] = cat.pk if cat else None
    else:
        fields["product_category_id"] = None
    return fields


# ── Bulk action: export selected templates as JSON ─────────────────────────────


def export_templates_as_json(modeladmin, request, queryset):
    payload = {
        "version": _EXPORT_VERSION,
        "templates": [_tmpl_to_dict(t) for t in queryset.order_by("name")],
    }
    resp = HttpResponse(json.dumps(payload, indent=2), content_type="application/json")
    resp["Content-Disposition"] = 'attachment; filename="imposition_templates.json"'
    return resp


export_templates_as_json.short_description = "Export selected templates as JSON"


@admin.register(ImpositionTemplate)
class ImpositionTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "product_category",
        "cut_size",
        "sheet_size",
        "columns",
        "rows",
    ]
    list_filter = ["product_category", "cut_size", "sheet_size"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [RecentPrintJobInline]
    change_list_template = "admin/impose/impositiontemplate/change_list.html"
    actions = [export_templates_as_json]
    fieldsets = [
        (
            None,
            {
                "fields": ["name", "product_category", "notes"],
            },
        ),
        (
            "Sizes",
            {
                "fields": [("cut_size", "sheet_size"), "bleed"],
            },
        ),
        (
            "Grid",
            {
                "fields": [("columns", "rows")],
            },
        ),
        (
            "Barcode",
            {
                "fields": [
                    "print_barcode",
                    ("barcode_x", "barcode_y"),
                    ("barcode_width", "barcode_height"),
                ],
            },
        ),
        (
            "Linked Presets",
            {
                "fields": [("cutter_program", "routing_preset")],
            },
        ),
        (
            "Timestamps",
            {
                "fields": [("created_at", "updated_at")],
                "classes": ["collapse"],
            },
        ),
    ]

    def get_actions(self, request):
        actions = super().get_actions(request)
        for category in ProductCategory.objects.order_by("name"):
            action_fn = _make_set_category_action(category)
            actions[action_fn.__name__] = (
                action_fn,
                action_fn.__name__,
                action_fn.short_description,
            )
        return actions

    def changelist_view(self, request, extra_context=None):
        """Handle the import-JSON POST and export-all GET from the changelist toolbar."""
        # Export All — triggered by a GET param so it doesn't interfere with filters
        if request.method == "GET" and "export_all_json" in request.GET:
            templates = ImpositionTemplate.objects.all().order_by("name")
            payload = {
                "version": _EXPORT_VERSION,
                "templates": [_tmpl_to_dict(t) for t in templates],
            }
            resp = HttpResponse(
                json.dumps(payload, indent=2), content_type="application/json"
            )
            resp["Content-Disposition"] = (
                'attachment; filename="imposition_templates.json"'
            )
            return resp

        # Import — triggered by a hidden POST field
        if request.method == "POST" and "import_json" in request.POST:
            upload = request.FILES.get("import_file")
            if not upload:
                self.message_user(request, "No file selected.", level=messages.ERROR)
            else:
                overwrite = request.POST.get("overwrite_import") == "on"
                try:
                    payload = json.loads(upload.read())
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    self.message_user(
                        request, f"Invalid JSON: {exc}", level=messages.ERROR
                    )
                    payload = None

                if payload is not None:
                    entries = (
                        payload
                        if isinstance(payload, list)
                        else payload.get("templates", [])
                    )
                    created = updated = skipped = errors = 0
                    for d in entries:
                        name = (d.get("name") or "").strip()
                        if not name:
                            errors += 1
                            continue
                        try:
                            fields = _dict_to_fields(d)
                        except Exception as exc:
                            self.message_user(
                                request,
                                f"Skipped '{name}': {exc}",
                                level=messages.WARNING,
                            )
                            errors += 1
                            continue
                        existing = ImpositionTemplate.objects.filter(name=name).first()
                        if existing:
                            if overwrite:
                                for k, v in fields.items():
                                    setattr(existing, k, v)
                                existing.save()
                                updated += 1
                            else:
                                skipped += 1
                        else:
                            ImpositionTemplate.objects.create(**fields)
                            created += 1

                    parts = []
                    if created:
                        parts.append(f"{created} created")
                    if updated:
                        parts.append(f"{updated} updated")
                    if skipped:
                        parts.append(f"{skipped} skipped (use Overwrite to replace)")
                    if errors:
                        parts.append(f"{errors} invalid entries ignored")
                    self.message_user(
                        request,
                        "Import complete: " + ", ".join(parts) + ".",
                        level=messages.SUCCESS,
                    )

        return super().changelist_view(request, extra_context=extra_context)
