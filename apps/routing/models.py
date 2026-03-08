from django.db import models


class RoutingPreset(models.Model):
    """Named set of printer options for routing a job to Fiery."""

    class DuplexMode(models.TextChoices):
        SIMPLEX = "simplex", "Simplex (1-sided)"
        DUPLEX_LONG = "duplex_long", "Duplex Long-Edge"
        DUPLEX_SHORT = "duplex_short", "Duplex Short-Edge"

    class ColorMode(models.TextChoices):
        COLOR = "color", "Color"
        GRAYSCALE = "grayscale", "Grayscale"

    name = models.CharField(max_length=100, unique=True)
    printer_queue = models.CharField(
        max_length=200, default="fiery", help_text="LPD queue name or IPP URI"
    )
    media_type = models.CharField(
        max_length=100, blank=True, help_text="e.g. 'Coated', 'Uncoated'"
    )
    media_size = models.CharField(max_length=50, blank=True, help_text="e.g. '12.5x19'")
    duplex = models.CharField(
        max_length=20, choices=DuplexMode.choices, default=DuplexMode.SIMPLEX
    )
    color_mode = models.CharField(
        max_length=20, choices=ColorMode.choices, default=ColorMode.COLOR
    )
    tray = models.CharField(max_length=50, blank=True)
    copies = models.PositiveSmallIntegerField(default=1)
    extra_lpr_options = models.TextField(
        blank=True, help_text="Additional -o key=value options, one per line"
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Routing Preset"
        verbose_name_plural = "Routing Presets"

    def __str__(self):
        return self.name
