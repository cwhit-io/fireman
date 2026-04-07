import json

from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html

from apps.jobs.models import PrintJob
from core.admin_mixins import ImportExportAdminMixin

from .models import POINTS_PER_INCH, ImpositionTemplate, PrintSize, ProductCategory


def _published_icon(published: bool) -> str:
    if published:
        return format_html(
            '<span style="color:#16a34a;font-weight:600;">&#x2713; Published</span>'
        )
    return format_html(
        '<span style="color:#9ca3af;">&#x2013; Draft</span>'
    )


@admin.action(description="Publish selected")
def publish_selected(modeladmin, request, queryset):
    updated = queryset.update(is_published=True)
    modeladmin.message_user(request, f"{updated} item(s) published.", messages.SUCCESS)


@admin.action(description="Unpublish selected")
def unpublish_selected(modeladmin, request, queryset):
    updated = queryset.update(is_published=False)
    modeladmin.message_user(request, f"{updated} item(s) unpublished.", messages.SUCCESS)


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
class ProductCategoryAdmin(ImportExportAdminMixin, admin.ModelAdmin):
    list_display = ["name", "description"]
    search_fields = ["name"]
    import_label = "Product Categories"
    export_filename = "product_categories.json"
    export_key = "product_categories"

    def obj_to_dict(self, obj):
        return {"name": obj.name, "description": obj.description}

    def dict_to_obj(self, d, overwrite):
        name = (d.get("name") or "").strip()
        if not name:
            return ("error", "Skipped entry with missing name.")
        existing = ProductCategory.objects.filter(name=name).first()
        if existing:
            if overwrite:
                existing.description = d.get("description", "")
                existing.save()
                return ("updated", None)
            return ("skipped", None)
        ProductCategory.objects.create(name=name, description=d.get("description", ""))
        return ("created", None)


_PT = POINTS_PER_INCH


@admin.register(PrintSize)
class PrintSizeAdmin(ImportExportAdminMixin, admin.ModelAdmin):
    list_display = ["name", "category", "size_type", "width", "height", "published_status", "thumbnail_preview"]
    list_filter = ["is_published", "size_type", "category"]
    search_fields = ["name"]
    import_label = "Print Sizes"
    export_filename = "print_sizes.json"
    export_key = "print_sizes"
    actions = [publish_selected, unpublish_selected]
    fieldsets = [
        (None, {"fields": ["name", "category", "size_type", ("width", "height"), "is_published"]}),
        ("Design Resources", {"fields": ["thumbnail", "canva_template_url"]}),
    ]

    @admin.display(description="Status")
    def published_status(self, obj):
        return _published_icon(obj.is_published)

    @admin.display(description="Thumbnail")
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="height:40px;width:auto;border-radius:3px;">',
                obj.thumbnail.url,
            )
        return "—"

    def obj_to_dict(self, obj):
        return {
            "name": obj.name,
            "width": round(float(obj.width) / _PT, 6),
            "height": round(float(obj.height) / _PT, 6),
            "size_type": obj.size_type,
        }

    def dict_to_obj(self, d, overwrite):
        name = (d.get("name") or "").strip()
        if not name:
            return ("error", "Skipped entry with missing name.")
        try:
            width_pts = round(float(d["width"]) * _PT, 3)
            height_pts = round(float(d["height"]) * _PT, 3)
        except (KeyError, TypeError, ValueError) as exc:
            return ("error", f"Skipped '{name}': invalid width/height — {exc}")
        size_type = d.get("size_type", "both")
        existing = PrintSize.objects.filter(name=name).first()
        if existing:
            if overwrite:
                existing.width = width_pts
                existing.height = height_pts
                existing.size_type = size_type
                existing.save()
                return ("updated", None)
            return ("skipped", None)
        PrintSize.objects.create(
            name=name, width=width_pts, height=height_pts, size_type=size_type
        )
        return ("created", None)


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
        "cutter_program",
        "duplo_code",
        "columns",
        "rows",
        "published_status",
    ]
    list_filter = ["is_published", "product_category", "cut_size", "sheet_size"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [RecentPrintJobInline]
    change_list_template = "admin/impose/impositiontemplate/change_list.html"
    actions = [export_templates_as_json, publish_selected, unpublish_selected]
    fieldsets = [
        (
            None,
            {
                "fields": ["name", "product_category", "is_published", "notes"],
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
                    "cutter_program",
                    "print_barcode",
                    ("barcode_x", "barcode_y"),
                    ("barcode_width", "barcode_height"),
                ],
            },
        ),
        (
            "Printer Presets",
            {
                "fields": [("routing_preset")],
            },
        ),
        (
            "Options",
            {
                "fields": ["allow_mailmerge"],
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

    @admin.display(description="Status")
    def published_status(self, obj):
        return _published_icon(obj.is_published)

    @admin.display(description="Duplo Code")
    def duplo_code(self, obj):
        return obj.cutter_program.duplo_code if obj.cutter_program else None

    def get_urls(self):
        custom = [
            path(
                "layout-preview/",
                self.admin_site.admin_view(self.layout_preview_view),
                name="impose_impositiontemplate_layout_preview",
            ),
        ]
        return custom + super().get_urls()

    def layout_preview_view(self, request):
        """Return an SVG snippet for the live layout preview panel."""
        from apps.impose.views import _build_preview_svg

        PT = POINTS_PER_INCH

        def _pts_to_in(key, default=0.0):
            try:
                v = float(request.POST.get(key) or 0)
                return v / PT if v else default
            except (TypeError, ValueError):
                return default

        cut_w_in = cut_h_in = 0.0
        sheet_w_in = sheet_h_in = 0.0

        cut_size_id = (request.POST.get("cut_size") or "").strip()
        if cut_size_id:
            try:
                cs = PrintSize.objects.get(pk=int(cut_size_id))
                cut_w_in = float(cs.width) / PT
                cut_h_in = float(cs.height) / PT
            except (PrintSize.DoesNotExist, ValueError):
                pass

        sheet_size_id = (request.POST.get("sheet_size") or "").strip()
        if sheet_size_id:
            try:
                ss = PrintSize.objects.get(pk=int(sheet_size_id))
                sheet_w_in = float(ss.width) / PT
                sheet_h_in = float(ss.height) / PT
            except (PrintSize.DoesNotExist, ValueError):
                pass

        bx_raw = (request.POST.get("barcode_x") or "").strip()
        by_raw = (request.POST.get("barcode_y") or "").strip()

        data = {
            "cut_width": str(cut_w_in) if cut_w_in else "",
            "cut_height": str(cut_h_in) if cut_h_in else "",
            "sheet_width": str(sheet_w_in),
            "sheet_height": str(sheet_h_in),
            "bleed": str(_pts_to_in("bleed")),
            "columns": request.POST.get("columns") or "1",
            "rows": request.POST.get("rows") or "1",
            "barcode_x": str(_pts_to_in("barcode_x")) if bx_raw else "",
            "barcode_y": str(_pts_to_in("barcode_y")) if by_raw else "",
            "barcode_width": str(_pts_to_in("barcode_width", 1.25)),
            "barcode_height": str(_pts_to_in("barcode_height", 0.35)),
        }
        return HttpResponse(_build_preview_svg(data), content_type="text/html")

    def _initial_preview_svg(self, tmpl):
        """Build the initial SVG for an existing template instance."""
        from apps.impose.views import _build_preview_svg

        PT = POINTS_PER_INCH

        def _in(pts):
            return str(round(float(pts) / PT, 6)) if pts is not None else ""

        if tmpl.cut_size_id:
            cut_w = _in(tmpl.cut_size.width)
            cut_h = _in(tmpl.cut_size.height)
        else:
            cut_w = _in(tmpl.cut_width)
            cut_h = _in(tmpl.cut_height)

        if tmpl.sheet_size_id:
            sheet_w = _in(tmpl.sheet_size.width)
            sheet_h = _in(tmpl.sheet_size.height)
        else:
            sheet_w = _in(tmpl.sheet_width)
            sheet_h = _in(tmpl.sheet_height)

        return _build_preview_svg(
            {
                "cut_width": cut_w,
                "cut_height": cut_h,
                "sheet_width": sheet_w,
                "sheet_height": sheet_h,
                "bleed": _in(tmpl.bleed),
                "columns": str(tmpl.columns),
                "rows": str(tmpl.rows),
                "barcode_x": _in(tmpl.barcode_x),
                "barcode_y": _in(tmpl.barcode_y),
                "barcode_width": _in(tmpl.barcode_width),
                "barcode_height": _in(tmpl.barcode_height),
            }
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["layout_preview_url"] = reverse(
            "admin:impose_impositiontemplate_layout_preview"
        )
        if object_id:
            try:
                tmpl = ImpositionTemplate.objects.select_related(
                    "cut_size", "sheet_size"
                ).get(pk=object_id)
                extra_context["preview_svg"] = self._initial_preview_svg(tmpl)
            except ImpositionTemplate.DoesNotExist:
                pass
        return super().changeform_view(request, object_id, form_url, extra_context)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "cut_size":
            kwargs["queryset"] = PrintSize.objects.filter(
                size_type__in=[PrintSize.SizeType.CUT, PrintSize.SizeType.BOTH]
            ).order_by("name")
        elif db_field.name == "sheet_size":
            kwargs["queryset"] = PrintSize.objects.filter(
                size_type__in=[PrintSize.SizeType.SHEET, PrintSize.SizeType.BOTH]
            ).order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """Copy dimensions from the selected PrintSize FKs into the scalar fields."""
        if obj.sheet_size_id:
            ss = obj.sheet_size
            obj.sheet_width = ss.width
            obj.sheet_height = ss.height
        if obj.cut_size_id:
            cs = obj.cut_size
            obj.cut_width = cs.width
            obj.cut_height = cs.height
        super().save_model(request, obj, form, change)

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
