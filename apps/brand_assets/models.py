from django.db import models


class BrandAssetCategory(models.Model):
    """Groups brand assets (e.g. "Logos", "Icons", "Marks")."""

    name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0, help_text="Display order (ascending).")

    class Meta:
        verbose_name = "Asset Category"
        verbose_name_plural = "Asset Categories"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


def _svg_upload_path(instance, filename):
    return f"brand_assets/svg/{filename}"


class BrandAsset(models.Model):
    """A single brand asset SVG file available for download."""

    category = models.ForeignKey(
        BrandAssetCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assets",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    svg_file = models.FileField(
        upload_to=_svg_upload_path,
        help_text="Upload the asset as an SVG file.",
    )
    order = models.PositiveSmallIntegerField(default=0, help_text="Display order (ascending).")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Brand Asset"
        verbose_name_plural = "Brand Assets"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class BrandColor(models.Model):
    """A brand color swatch shown on the brand assets page."""

    name = models.CharField(max_length=100, help_text="e.g. 'Primary Blue'")
    hex_value = models.CharField(
        max_length=7,
        help_text="Hex color code including #, e.g. #1A2B3C",
    )
    cmyk_label = models.CharField(
        max_length=40,
        blank=True,
        help_text="Optional CMYK values, e.g. 'C:100 M:80 Y:0 K:20'",
    )
    pantone_label = models.CharField(
        max_length=40,
        blank=True,
        help_text="Optional Pantone swatch name, e.g. 'PMS 286 C'",
    )
    rgb_label = models.CharField(
        max_length=40,
        blank=True,
        help_text="Optional RGB values, e.g. 'R:26 G:43 B:60'",
    )
    order = models.PositiveSmallIntegerField(default=0, help_text="Display order (ascending).")

    class Meta:
        verbose_name = "Brand Color"
        verbose_name_plural = "Brand Colors"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.hex_value})"
