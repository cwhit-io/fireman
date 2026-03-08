from django.db import models


class Rule(models.Model):
    """Auto-routing ruleset that matches job attributes and applies one or more actions."""

    class ConditionType(models.TextChoices):
        PAGE_SIZE = "page_size", "Page Size (W×H in)"
        PAGE_COUNT = "page_count", "Page Count"
        FILENAME = "filename", "Filename Pattern"
        PRODUCT_TYPE = "product_type", "Product Type"

    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(
        default=10, help_text="Lower number = higher priority"
    )
    condition_type = models.CharField(max_length=30, choices=ConditionType.choices)
    condition_value = models.CharField(
        max_length=255, help_text="Value to match (exact or pattern)"
    )

    # Actions — any combination may be applied from a single ruleset
    imposition_template = models.ForeignKey(
        "impose.ImpositionTemplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rules",
        help_text="Gangup / imposition template to apply",
    )
    cutter_program = models.ForeignKey(
        "cutter.CutterProgram",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rules",
        help_text="Cutter / barcode program to assign",
    )
    routing_preset = models.ForeignKey(
        "routing.RoutingPreset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rules",
        help_text="Printer preset to route to",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "Ruleset"
        verbose_name_plural = "Rulesets"

    def __str__(self):
        return f"[{self.priority}] {self.name}: {self.condition_type}={self.condition_value}"
