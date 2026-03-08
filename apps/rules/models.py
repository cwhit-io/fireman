from django.db import models


class Rule(models.Model):
    """Named ruleset that assigns actions (template, cutter, printer) to a print job."""

    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

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
    # Size / category filters — used to select appropriate imposition templates
    cut_size = models.ForeignKey(
        "impose.PrintSize",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rules_cut",
        help_text="Cut size (finished product dimensions) for this ruleset",
    )
    sheet_size = models.ForeignKey(
        "impose.PrintSize",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rules_sheet",
        help_text="Sheet size (press sheet dimensions) for this ruleset",
    )
    product_category = models.ForeignKey(
        "impose.ProductCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rules",
        help_text="Product category for this ruleset (e.g. Bookmarks, Postcards)",
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
        ordering = ["name"]
        verbose_name = "Ruleset"
        verbose_name_plural = "Rulesets"

    def __str__(self):
        return self.name
