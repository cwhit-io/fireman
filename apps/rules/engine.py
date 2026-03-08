"""
Rules engine: apply ruleset actions to a PrintJob.

Auto-routing (condition matching / priority ordering) has been removed.
Rulesets are now applied manually by the operator.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


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
