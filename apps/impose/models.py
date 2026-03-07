from django.db import models


class ImpositionTemplate(models.Model):
    """Defines how pages should be imposed onto a press sheet."""

    class LayoutType(models.TextChoices):
        TWO_UP = "2up", "2-Up"
        FOUR_UP = "4up", "4-Up"
        EIGHT_UP = "8up", "8-Up"
        CUT_STACK = "cut_stack", "Cut & Stack"
        STEP_REPEAT = "step_repeat", "Step & Repeat"
        BUSINESS_CARD = "business_card", "Business Card (21-up)"
        POSTCARD = "postcard", "Postcard"
        RACK_CARD = "rack_card", "Rack Card"
        CUSTOM = "custom", "Custom"

    name = models.CharField(max_length=100, unique=True)
    layout_type = models.CharField(max_length=20, choices=LayoutType.choices)
    sheet_width = models.DecimalField(max_digits=8, decimal_places=3, help_text="Points (1 pt = 1/72 in)")
    sheet_height = models.DecimalField(max_digits=8, decimal_places=3, help_text="Points")
    bleed = models.DecimalField(max_digits=6, decimal_places=3, default=0, help_text="Points")
    margin_top = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    margin_right = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    margin_bottom = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    margin_left = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    barcode_x = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Barcode X position in points")
    barcode_y = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Barcode Y position in points")
    columns = models.PositiveSmallIntegerField(default=1)
    rows = models.PositiveSmallIntegerField(default=1)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Imposition Template"
        verbose_name_plural = "Imposition Templates"

    def __str__(self):
        return self.name
