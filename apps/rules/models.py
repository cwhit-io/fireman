from django.db import models


class Rule(models.Model):
    """Auto-routing rule that matches job attributes and applies actions."""

    class ConditionType(models.TextChoices):
        PAGE_SIZE = "page_size", "Page Size (WxH pts)"
        PAGE_COUNT = "page_count", "Page Count"
        FILENAME = "filename", "Filename Pattern"
        PRODUCT_TYPE = "product_type", "Product Type"

    class ActionType(models.TextChoices):
        APPLY_TEMPLATE = "apply_template", "Apply Imposition Template"
        ASSIGN_CUTTER = "assign_cutter", "Assign Cutter Program"
        ROUTE_TO_PRINTER = "route_to_printer", "Route to Printer Preset"

    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(default=10, help_text="Lower number = higher priority")
    condition_type = models.CharField(max_length=30, choices=ConditionType.choices)
    condition_value = models.CharField(max_length=255, help_text="Value to match (exact or pattern)")
    action_type = models.CharField(max_length=30, choices=ActionType.choices)
    action_value = models.CharField(max_length=255, help_text="ID or name of the target object")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "Rule"
        verbose_name_plural = "Rules"

    def __str__(self):
        return f"[{self.priority}] {self.name}: {self.condition_type}={self.condition_value} → {self.action_type}"
