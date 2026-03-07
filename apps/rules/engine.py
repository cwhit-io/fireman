"""
Rules engine: evaluate active rules against a PrintJob and apply matching actions.
"""
from __future__ import annotations

import fnmatch
import logging

logger = logging.getLogger(__name__)


def _matches(rule, job) -> bool:
    """Return True if *job* satisfies *rule*'s condition."""
    from apps.rules.models import Rule

    ct = rule.condition_type
    cv = rule.condition_value.strip()

    if ct == Rule.ConditionType.PAGE_SIZE:
        # condition_value format: "WxH" in points, e.g. "612x792"
        if not (job.page_width and job.page_height):
            return False
        try:
            cw, ch = (float(v) for v in cv.lower().split("x"))
        except ValueError:
            return False
        return (
            abs(float(job.page_width) - cw) < 1.0
            and abs(float(job.page_height) - ch) < 1.0
        )

    if ct == Rule.ConditionType.PAGE_COUNT:
        # Support exact match or comparison like ">=4"
        if job.page_count is None:
            return False
        try:
            if cv.startswith(">="):
                return job.page_count >= int(cv[2:])
            if cv.startswith("<="):
                return job.page_count <= int(cv[2:])
            if cv.startswith(">"):
                return job.page_count > int(cv[1:])
            if cv.startswith("<"):
                return job.page_count < int(cv[1:])
            return job.page_count == int(cv)
        except ValueError:
            return False

    if ct == Rule.ConditionType.FILENAME:
        return fnmatch.fnmatch(job.name.lower(), cv.lower())

    if ct == Rule.ConditionType.PRODUCT_TYPE:
        return job.product_type.strip().lower() == cv.lower()

    return False


def _apply(rule, job) -> None:
    """Apply *rule*'s action to *job*."""
    from apps.rules.models import Rule

    at = rule.action_type
    av = rule.action_value.strip()

    if at == Rule.ActionType.APPLY_TEMPLATE:
        from apps.impose.models import ImpositionTemplate
        try:
            tmpl = ImpositionTemplate.objects.get(pk=int(av))
            job.imposition_template = tmpl
            logger.info("Rule '%s': applied template '%s' to job %s", rule.name, tmpl.name, job.pk)
        except (ImpositionTemplate.DoesNotExist, ValueError):
            logger.warning("Rule '%s': template id=%s not found", rule.name, av)

    elif at == Rule.ActionType.ASSIGN_CUTTER:
        from apps.cutter.models import CutterProgram
        try:
            prog = CutterProgram.objects.get(pk=int(av))
            job.cutter_program = prog
            logger.info("Rule '%s': assigned cutter '%s' to job %s", rule.name, prog.name, job.pk)
        except (CutterProgram.DoesNotExist, ValueError):
            logger.warning("Rule '%s': cutter program id=%s not found", rule.name, av)

    elif at == Rule.ActionType.ROUTE_TO_PRINTER:
        from apps.routing.models import RoutingPreset
        try:
            preset = RoutingPreset.objects.get(pk=int(av))
            job.routing_preset = preset
            logger.info("Rule '%s': routed job %s to preset '%s'", rule.name, job.pk, preset.name)
        except (RoutingPreset.DoesNotExist, ValueError):
            logger.warning("Rule '%s': routing preset id=%s not found", rule.name, av)


def apply_rules(job) -> None:
    """Evaluate all active rules against *job* in priority order and save changes."""
    from apps.rules.models import Rule

    rules = Rule.objects.filter(active=True).order_by("priority")
    changed = False
    for rule in rules:
        if _matches(rule, job):
            _apply(rule, job)
            changed = True

    if changed:
        job.save(update_fields=["imposition_template", "cutter_program", "routing_preset"])
