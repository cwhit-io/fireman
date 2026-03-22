"""
ImportExportAdminMixin
======================
Drop-in mixin for Django ModelAdmin classes that adds JSON import/export
to the changelist page.

Subclasses must set the class attributes and implement obj_to_dict /
dict_to_obj (see docstrings below).
"""

import json

from django.contrib import messages
from django.http import HttpResponse


class ImportExportAdminMixin:
    """
    Adds JSON import & export to any ModelAdmin changelist.

    Required class attributes
    -------------------------
    import_label : str
        Human label shown in the import panel heading, e.g. "Routing Presets".
    export_filename : str
        Suggested download filename, e.g. "routing_presets.json".
    export_key : str
        Top-level list key in the JSON envelope, e.g. "routing_presets".

    Optional class attributes
    -------------------------
    export_note : str | None
        If set, included in exported JSON as a ``_note`` field.
    import_note : str | None
        If set, displayed inside the import panel as an info callout.

    Required methods
    ----------------
    obj_to_dict(obj) -> dict
        Serialize one model instance to a plain dict.
    dict_to_obj(d, overwrite) -> tuple[str, str | None]
        Deserialize one dict.  Returns ``(action, warning_msg)`` where
        *action* is one of ``'created' | 'updated' | 'skipped' | 'error'``
        and *warning_msg* is an optional per-item message (or None).
    """

    change_list_template = "admin/common/import_export_change_list.html"
    import_label = "Items"
    export_filename = "export.json"
    export_key = "items"
    export_note = None
    import_note = None

    # ── Actions ──────────────────────────────────────────────────────────────

    def get_actions(self, request):
        actions = super().get_actions(request)

        def _export_selected(modeladmin, request, queryset):
            payload = {
                "version": 1,
                modeladmin.export_key: [
                    modeladmin.obj_to_dict(o) for o in queryset
                ],
            }
            if modeladmin.export_note:
                payload["_note"] = modeladmin.export_note
            resp = HttpResponse(
                json.dumps(payload, indent=2), content_type="application/json"
            )
            resp["Content-Disposition"] = (
                f'attachment; filename="{modeladmin.export_filename}"'
            )
            return resp

        _export_selected.short_description = "Export selected as JSON"
        actions["export_selected_json"] = (
            _export_selected,
            "export_selected_json",
            _export_selected.short_description,
        )
        return actions

    # ── Changelist (export-all + import) ─────────────────────────────────────

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.setdefault("import_label", self.import_label)
        if self.import_note:
            extra_context.setdefault("import_note", self.import_note)

        # Export All
        if request.method == "GET" and "export_all_json" in request.GET:
            payload = {
                "version": 1,
                self.export_key: [
                    self.obj_to_dict(o) for o in self.get_queryset(request)
                ],
            }
            if self.export_note:
                payload["_note"] = self.export_note
            resp = HttpResponse(
                json.dumps(payload, indent=2), content_type="application/json"
            )
            resp["Content-Disposition"] = (
                f'attachment; filename="{self.export_filename}"'
            )
            return resp

        # Import
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
                    return super().changelist_view(request, extra_context)

                entries = (
                    payload
                    if isinstance(payload, list)
                    else payload.get(self.export_key, [])
                )
                counts = {"created": 0, "updated": 0, "skipped": 0, "error": 0}
                for d in entries:
                    try:
                        action, msg = self.dict_to_obj(d, overwrite)
                    except Exception as exc:
                        counts["error"] += 1
                        self.message_user(
                            request, f"Import error: {exc}", level=messages.WARNING
                        )
                        continue
                    counts[action] = counts.get(action, 0) + 1
                    if msg:
                        self.message_user(request, msg, level=messages.WARNING)

                parts = []
                if counts["created"]:
                    parts.append(f"{counts['created']} created")
                if counts["updated"]:
                    parts.append(f"{counts['updated']} updated")
                if counts["skipped"]:
                    parts.append(
                        f"{counts['skipped']} skipped (use Overwrite to replace)"
                    )
                if counts["error"]:
                    parts.append(f"{counts['error']} invalid entries ignored")
                self.message_user(
                    request,
                    "Import complete: "
                    + (", ".join(parts) or "nothing to do")
                    + ".",
                    level=messages.SUCCESS,
                )

        return super().changelist_view(request, extra_context)
