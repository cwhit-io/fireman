"""
Custom admin form for RoutingPreset.

Replaces the raw fiery_options JSONField textarea with organised sections of
<select> dropdowns, one per PPD key.  POST values are collected under the name
``fiery_opt_<KEY>`` and packed back into the JSON dict on save.
"""

from __future__ import annotations

import json

from django import forms
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

from .fiery_options import FIERY_OPTION_SECTIONS
from .models import RoutingPreset

# Sections that should be expanded (open) by default in the admin form.
_DEFAULT_OPEN = {
    "Media",
    "Print Queue Action",
    "Color",
    "Layout",
    "Output & Delivery",
    "Finishing",
}


class FieryOptionsWidget(forms.Widget):
    """
    Renders the fiery_options JSON dict as collapsible <details> sections,
    each containing a responsive grid of <select> dropdowns.

    POST values are read from ``fiery_opt_<PPD_KEY>`` fields; empty values
    (the "— printer default —" choice) are omitted from the saved dict.
    """

    def render(self, name, value, attrs=None, renderer=None):
        # Normalise incoming value to a plain dict.
        if isinstance(value, str):
            try:
                current: dict = json.loads(value) if value else {}
            except (json.JSONDecodeError, TypeError):
                current = {}
        elif isinstance(value, dict):
            current = value
        else:
            current = {}

        parts = ['<div class="fiery-opts-widget">']

        for section_title, options in FIERY_OPTION_SECTIONS:
            # Auto-open if any option in this section already has a value set,
            # or if the section is in the default-open set.
            has_value = any(current.get(key, "") for key, _, _ in options)
            open_attr = " open" if has_value or section_title in _DEFAULT_OPEN else ""

            parts.append(f'<details class="fiery-section"{open_attr}>')
            parts.append(
                f'<summary class="fiery-section-title">'
                f"{conditional_escape(section_title)}</summary>"
            )
            parts.append('<div class="fiery-section-grid">')

            for key, label, choices in options:
                field_name = f"fiery_opt_{key}"
                current_val = current.get(key, "")

                parts.append('<div class="fiery-field-group">')
                parts.append(
                    f'<label for="id_{field_name}">'
                    f"{conditional_escape(label)}</label>"
                )
                parts.append(
                    f'<select id="id_{field_name}" name="{field_name}">'
                )
                for val, lbl in choices:
                    selected = " selected" if val == current_val else ""
                    parts.append(
                        f"<option value=\"{conditional_escape(val)}\"{selected}>"
                        f"{conditional_escape(lbl)}</option>"
                    )
                parts.append("</select>")
                parts.append("</div>")  # fiery-field-group

            parts.append("</div>")  # fiery-section-grid
            parts.append("</details>")

        parts.append("</div>")  # fiery-opts-widget
        return mark_safe("".join(parts))

    def value_from_datadict(self, data, files, name):
        """Collect fiery_opt_<KEY> POST fields into a dict (skip empty values)."""
        result: dict[str, str] = {}
        for _, options in FIERY_OPTION_SECTIONS:
            for key, _, _ in options:
                val = data.get(f"fiery_opt_{key}", "").strip()
                if val:
                    result[key] = val
        return result

    class Media:
        css = {
            "all": ("routing/admin_fiery_options.css",),
        }


class FieryOptionsFormField(forms.Field):
    """
    Form field that uses FieryOptionsWidget and passes a Python dict through
    validation unchanged (no JSON serialisation/deserialisation needed here
    because the widget already returns a dict from value_from_datadict).
    """

    widget = FieryOptionsWidget

    def to_python(self, value):
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON for Fiery options.")
        return {}

    def prepare_value(self, value):
        """Ensure the widget always receives a dict, not a raw JSON string."""
        if isinstance(value, str):
            try:
                return json.loads(value) if value else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return value or {}


class RoutingPresetAdminForm(forms.ModelForm):
    fiery_options = FieryOptionsFormField(
        required=False,
        label="Fiery Print Options",
        help_text=(
            "Options left at \u201c\u2014 printer default \u2014\u201d are not sent to the"
            " printer. Only explicitly selected values are included in the"
            " print command."
        ),
    )

    class Meta:
        model = RoutingPreset
        fields = "__all__"
