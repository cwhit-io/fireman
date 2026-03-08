"""
Rules engine: evaluate active rulesets against a PrintJob and apply matching actions.
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
        # condition_value format: "WxH" in inches, e.g. "8.5x11" (letter) or "11x17" (tabloid)
        if not (job.page_width and job.page_height):
            return False
        try:
            cw_in, ch_in = (float(v) for v in cv.lower().split("x"))
            cw_pt = cw_in * 72.0
            ch_pt = ch_in * 72.0
        except ValueError:
            return False
        return (
            abs(float(job.page_width) - cw_pt) < 1.0
            and abs(float(job.page_height) - ch_pt) < 1.0
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
        return (job.product_type or "").strip().lower() == cv.lower()

    return False


def _apply(rule, job) -> None:
    """Apply all of *rule*'s configured actions to *job*."""
    if rule.imposition_template_id:
        job.imposition_template = rule.imposition_template
        logger.info(
            "Ruleset '%s': applied template '%s' to job %s",
            rule.name,
            rule.imposition_template.name,
            job.pk,
        )

    if rule.cutter_program_id:
        job.cutter_program = rule.cutter_program
        logger.info(
            "Ruleset '%s': assigned cutter '%s' to job %s",
            rule.name,
            rule.cutter_program.name,
            job.pk,
        )

    if rule.routing_preset_id:
        job.routing_preset = rule.routing_preset
        logger.info(
            "Ruleset '%s': routed job %s to preset '%s'",
            rule.name,
            job.pk,
            rule.routing_preset.name,
        )


def apply_rules(job) -> None:
    """Evaluate all active rulesets against *job* in priority order and save changes."""
    from apps.rules.models import Rule

    rules = Rule.objects.filter(active=True).select_related(
        "imposition_template", "cutter_program", "routing_preset"
    ).order_by("priority")
    changed = False
    for rule in rules:
        if _matches(rule, job):
            _apply(rule, job)
            changed = True

    if changed:
        job.save(update_fields=["imposition_template", "cutter_program", "routing_preset"])
