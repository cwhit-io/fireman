from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView

from apps.impose.models import ImpositionTemplate, PrintSize, ProductCategory
from apps.routing.models import RoutingPreset

from .models import Rule


def _build_form_context(cut_size_id=None, sheet_size_id=None, product_category_id=None):
    """Return available action targets and choice lists for the ruleset form.

    When size/category filter IDs are provided the template list is narrowed to
    only those that match all supplied filters.
    """
    templates_qs = ImpositionTemplate.objects.select_related(
        "cutter_program", "product_category", "cut_size", "sheet_size"
    ).order_by("name")

    if cut_size_id:
        templates_qs = templates_qs.filter(cut_size_id=cut_size_id)
    if sheet_size_id:
        templates_qs = templates_qs.filter(sheet_size_id=sheet_size_id)
    if product_category_id:
        templates_qs = templates_qs.filter(product_category_id=product_category_id)

    return {
        "templates": templates_qs,
        "all_templates": ImpositionTemplate.objects.select_related(
            "cutter_program", "product_category", "cut_size", "sheet_size"
        ).order_by("name"),
        "presets": RoutingPreset.objects.filter(active=True).order_by("name"),
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
            "imposition_template": str(rule.imposition_template_id)
            if rule.imposition_template_id
            else "",
            "routing_preset": str(rule.routing_preset_id)
            if rule.routing_preset_id
            else "",
            "cut_size": str(rule.cut_size_id) if rule.cut_size_id else "",
            "sheet_size": str(rule.sheet_size_id) if rule.sheet_size_id else "",
            "product_category": str(rule.product_category_id)
            if rule.product_category_id
            else "",
            "active": "on" if rule.active else "",
        }
    return {
        "name": "",
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
    return errors


def _fk_or_none(data, key):
    val = data.get(key, "").strip()
    return int(val) if val else None


class RuleListView(ListView):
    model = Rule
    template_name = "rules/rule_list.html"
    context_object_name = "rules"

    def get_queryset(self):
        return Rule.objects.select_related(
            "imposition_template",
            "cutter_program",
            "routing_preset",
            "product_category",
            "cut_size",
            "sheet_size",
        ).order_by("name")


class RuleCreateView(View):
    template_name = "rules/rule_form.html"

    def get(self, request):
        ctx = _build_form_context()
        ctx["values"] = _get_initial_form_values()
        return render(request, self.template_name, ctx)

    def post(self, request):
        data = request.POST

        # HTMX filter request — re-render only the template dropdown
        if request.headers.get("HX-Request") and data.get("_filter_templates"):
            ctx = _build_form_context(
                cut_size_id=_fk_or_none(data, "cut_size"),
                sheet_size_id=_fk_or_none(data, "sheet_size"),
                product_category_id=_fk_or_none(data, "product_category"),
            )
            ctx["values"] = dict(data)
            from django.http import HttpResponse
            from django.template.loader import render_to_string

            html = render_to_string(
                "rules/_template_options.html", ctx, request=request
            )
            return HttpResponse(html)

        errors = _validate_rule_form(data)

        if not errors:
            rule = Rule.objects.create(
                name=data["name"].strip(),
                imposition_template_id=_fk_or_none(data, "imposition_template"),
                routing_preset_id=_fk_or_none(data, "routing_preset"),
                cut_size_id=_fk_or_none(data, "cut_size"),
                sheet_size_id=_fk_or_none(data, "sheet_size"),
                product_category_id=_fk_or_none(data, "product_category"),
                active=data.get("active") == "on",
            )
            messages.success(request, f"Ruleset '{rule.name}' created.")
            return redirect("rules:list")

        ctx = _build_form_context(
            cut_size_id=_fk_or_none(data, "cut_size"),
            sheet_size_id=_fk_or_none(data, "sheet_size"),
            product_category_id=_fk_or_none(data, "product_category"),
        )
        ctx["values"] = dict(data)
        ctx["errors"] = errors
        return render(request, self.template_name, ctx, status=400)


class RuleEditView(View):
    template_name = "rules/rule_form.html"

    def get(self, request, pk):
        rule = get_object_or_404(Rule, pk=pk)
        ctx = _build_form_context(
            cut_size_id=rule.cut_size_id,
            sheet_size_id=rule.sheet_size_id,
            product_category_id=rule.product_category_id,
        )
        ctx["rule"] = rule
        ctx["values"] = _get_initial_form_values(rule)
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        rule = get_object_or_404(Rule, pk=pk)
        data = request.POST

        # HTMX filter request — re-render only the template dropdown
        if request.headers.get("HX-Request") and data.get("_filter_templates"):
            ctx = _build_form_context(
                cut_size_id=_fk_or_none(data, "cut_size"),
                sheet_size_id=_fk_or_none(data, "sheet_size"),
                product_category_id=_fk_or_none(data, "product_category"),
            )
            ctx["values"] = dict(data)
            from django.http import HttpResponse
            from django.template.loader import render_to_string

            html = render_to_string(
                "rules/_template_options.html", ctx, request=request
            )
            return HttpResponse(html)

        errors = _validate_rule_form(data)

        if not errors:
            rule.name = data["name"].strip()
            rule.imposition_template_id = _fk_or_none(data, "imposition_template")
            rule.routing_preset_id = _fk_or_none(data, "routing_preset")
            rule.cut_size_id = _fk_or_none(data, "cut_size")
            rule.sheet_size_id = _fk_or_none(data, "sheet_size")
            rule.product_category_id = _fk_or_none(data, "product_category")
            rule.active = data.get("active") == "on"
            rule.save()
            messages.success(request, f"Ruleset '{rule.name}' updated.")
            return redirect("rules:list")

        ctx = _build_form_context(
            cut_size_id=_fk_or_none(data, "cut_size"),
            sheet_size_id=_fk_or_none(data, "sheet_size"),
            product_category_id=_fk_or_none(data, "product_category"),
        )
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
