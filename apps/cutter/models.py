from django.db import models


class CutterProgram(models.Model):
    """Represents a DC-646 cutter program."""

    name = models.CharField(max_length=100, unique=True)
    duplo_code = models.CharField(
        max_length=50, help_text="Program ID/barcode value for the DC-646"
    )
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Barcode placement on the imposed sheet (points, origin = bottom-left).
    # When set, the TIF barcode for this program is stamped at this position
    # during imposition, overriding any barcode coordinates on the template.
    barcode_x = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Barcode left edge on the sheet, in points (leave blank to use template default)",
    )
    barcode_y = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Barcode bottom edge on the sheet, in points (leave blank to use template default)",
    )
    # DC-646 barcode block defaults: 1.25\" × 0.35\"
    barcode_width = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=90.0,
        help_text='Barcode block width in points (default 90 pt = 1.25")',
    )
    barcode_height = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=25.2,
        help_text='Barcode block height in points (default 25.2 pt = 0.35")',
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Cutter Program"
        verbose_name_plural = "Cutter Programs"

    def __str__(self):
        return f"{self.name} ({self.duplo_code})"
