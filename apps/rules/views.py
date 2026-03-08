from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView

from apps.cutter.models import CutterProgram
from apps.impose.models import ImpositionTemplate
from apps.routing.models import RoutingPreset

from .models import Rule


def _build_form_context():
    """Return available action targets and choice lists for the rule form."""
    return {
        "templates": ImpositionTemplate.objects.order_by("name"),
        "cutters": CutterProgram.objects.filter(active=True).order_by("name"),
        "presets": RoutingPreset.objects.filter(active=True).order_by("name"),
        "condition_types": Rule.ConditionType.choices,
        "action_types": Rule.ActionType.choices,
    }


def _get_initial_form_values(rule=None):
    """Return a dict of initial form field values, optionally seeded from a rule."""
    if rule:
        return {
            "name": rule.name,
            "priority": str(rule.priority),
            "condition_type": rule.condition_type,
            "condition_value": rule.condition_value,
            "action_type": rule.action_type,
            "action_value": rule.action_value,
            "active": "on" if rule.active else "",
        }
    return {
        "name": "",
        "priority": "10",
        "condition_type": "",
        "condition_value": "",
        "action_type": "",
        "action_value": "",
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
    if not data.get("action_type", ""):
        errors["action_type"] = "Action type is required."
    if not data.get("action_value", "").strip():
        errors["action_value"] = "Action value is required."
    return errors


class RuleListView(ListView):
    model = Rule
    template_name = "rules/rule_list.html"
    context_object_name = "rules"


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
            rule = Rule.objects.create(
                name=data["name"].strip(),
                priority=priority,
                condition_type=data["condition_type"],
                condition_value=data["condition_value"].strip(),
                action_type=data["action_type"],
                action_value=data["action_value"].strip(),
                active=data.get("active") == "on",
            )
            messages.success(request, f"Rule '{rule.name}' created.")
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
            rule.action_type = data["action_type"]
            rule.action_value = data["action_value"].strip()
            rule.active = data.get("active") == "on"
            rule.save()
            messages.success(request, f"Rule '{rule.name}' updated.")
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
        messages.success(self.request, f"Rule '{rule.name}' deleted.")
        return super().form_valid(form)


class RuleToggleView(View):
    """Toggle active status via POST."""

    def post(self, request, pk):
        rule = get_object_or_404(Rule, pk=pk)
        rule.active = not rule.active
        rule.save(update_fields=["active"])
        state = "enabled" if rule.active else "disabled"
        messages.success(request, f"Rule '{rule.name}' {state}.")
        return redirect("rules:list")
