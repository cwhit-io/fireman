from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView

from apps.impose.models import ImpositionTemplate, PrintSize, ProductCategory
from apps.routing.models import RoutingPreset

from .models import Rule


def _build_form_context():
    """Return available action targets and choice lists for the ruleset form."""
    return {
        "templates": ImpositionTemplate.objects.select_related(
            "cutter_program", "product_category", "cut_size", "sheet_size"
        ).order_by("name"),
        "presets": RoutingPreset.objects.filter(active=True).order_by("name"),
        "condition_types": Rule.ConditionType.choices,
        "product_categories": ProductCategory.objects.order_by("name"),
        "cut_sizes": PrintSize.objects.filter(
            size_type__in=[PrintSize.SizeType.CUT, PrintSize.SizeType.BOTH]
        ).order_by("name"),
        "sheet_sizes": PrintSize.objects.filter(
            size_type__in=[PrintSize.SizeType.SHEET, PrintSize.SizeType.BOTH]
        ).order_by("name"),
    }


def _get_initial_form_values(rule=None):
    """Return a dict of initial form field values, optionally seeded from a rule."""
    if rule:
        return {
            "name": rule.name,
            "priority": str(rule.priority),
            "condition_type": rule.condition_type,
            "condition_value": rule.condition_value,
            "imposition_template": str(rule.imposition_template_id)
            if rule.imposition_template_id
            else "",
            "routing_preset": str(rule.routing_preset_id)
            if rule.routing_preset_id
            else "",
            "cut_size": str(rule.cut_size_id) if rule.cut_size_id else "",
            "sheet_size": str(rule.sheet_size_id) if rule.sheet_size_id else "",
            "product_category": str(rule.product_category_id) if rule.product_category_id else "",
            "active": "on" if rule.active else "",
        }
    return {
        "name": "",
        "priority": "10",
        "condition_type": "",
        "condition_value": "",
        "imposition_template": "",
        "routing_preset": "",
        "cut_size": "",
        "sheet_size": "",
        "product_category": "",
        "active": "on",
    }


def _validate_rule_form(data):
    errors = {}
    if not data.get("name", "").strip():
        errors["name"] = "Name is required."
    if not data.get("condition_type", ""):
        errors["condition_type"] = "Condition type is required."
    if not data.get("condition_value", "").strip():
        errors["condition_value"] = "Condition value is required."
    # At least one action must be selected
    has_action = any(
        [
            data.get("imposition_template"),
            data.get("routing_preset"),
        ]
    )
    if not has_action:
        errors["actions"] = (
            "At least one action (template or preset) is required."
        )
    return errors


class RuleListView(ListView):
    model = Rule
    template_name = "rules/rule_list.html"
    context_object_name = "rules"

    def get_queryset(self):
        return Rule.objects.select_related(
            "imposition_template", "cutter_program", "routing_preset"
        ).order_by("priority", "name")


class RuleCreateView(View):
    template_name = "rules/rule_form.html"

    def get(self, request):
        ctx = _build_form_context()
        ctx["values"] = _get_initial_form_values()
        return render(request, self.template_name, ctx)

    def post(self, request):
        data = request.POST
        errors = _validate_rule_form(data)

        if not errors:
            try:
                priority = int(data.get("priority", 10))
            except (ValueError, TypeError):
                priority = 10

            def _fk_or_none(key):
                val = data.get(key, "").strip()
                return int(val) if val else None

            rule = Rule.objects.create(
                name=data["name"].strip(),
                priority=priority,
                condition_type=data["condition_type"],
                condition_value=data["condition_value"].strip(),
                imposition_template_id=_fk_or_none("imposition_template"),
                routing_preset_id=_fk_or_none("routing_preset"),
                cut_size_id=_fk_or_none("cut_size"),
                sheet_size_id=_fk_or_none("sheet_size"),
                product_category_id=_fk_or_none("product_category"),
                active=data.get("active") == "on",
            )
            messages.success(request, f"Ruleset '{rule.name}' created.")
            return redirect("rules:list")

        ctx = _build_form_context()
        ctx["values"] = dict(data)
        ctx["errors"] = errors
        return render(request, self.template_name, ctx, status=400)


class RuleEditView(View):
    template_name = "rules/rule_form.html"

    def get(self, request, pk):
        rule = get_object_or_404(Rule, pk=pk)
        ctx = _build_form_context()
        ctx["rule"] = rule
        ctx["values"] = _get_initial_form_values(rule)
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        rule = get_object_or_404(Rule, pk=pk)
        data = request.POST
        errors = _validate_rule_form(data)

        if not errors:
            rule.name = data["name"].strip()
            try:
                rule.priority = int(data.get("priority", 10))
            except (ValueError, TypeError):
                rule.priority = 10
            rule.condition_type = data["condition_type"]
            rule.condition_value = data["condition_value"].strip()

            def _fk_or_none(key):
                val = data.get(key, "").strip()
                return int(val) if val else None

            rule.imposition_template_id = _fk_or_none("imposition_template")
            rule.routing_preset_id = _fk_or_none("routing_preset")
            rule.active = data.get("active") == "on"
            rule.save()
            messages.success(request, f"Ruleset '{rule.name}' updated.")
            return redirect("rules:list")

        ctx = _build_form_context()
        ctx["rule"] = rule
        ctx["values"] = dict(data)
        ctx["errors"] = errors
        return render(request, self.template_name, ctx, status=400)


class RuleDeleteView(DeleteView):
    model = Rule
    template_name = "rules/rule_confirm_delete.html"
    success_url = reverse_lazy("rules:list")

    def form_valid(self, form):
        rule = self.get_object()
        messages.success(self.request, f"Ruleset '{rule.name}' deleted.")
        return super().form_valid(form)


class RuleToggleView(View):
    """Toggle active status via POST."""

    def post(self, request, pk):
        rule = get_object_or_404(Rule, pk=pk)
        rule.active = not rule.active
        rule.save(update_fields=["active"])
        state = "enabled" if rule.active else "disabled"
        messages.success(request, f"Ruleset '{rule.name}' {state}.")
        return redirect("rules:list")
