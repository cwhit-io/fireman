from django.core.exceptions import ValidationError
from django.db import models

POINTS_PER_INCH = 72.0


class ProductCategory(models.Model):
    """Lookup table for product categories (e.g. Bookmarks, Postcards, Business Cards)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"

    def __str__(self):
        return self.name


class PrintSize(models.Model):
    """Named size for cut sizes (finished product) or press sheet sizes."""

    class SizeType(models.TextChoices):
        CUT = "cut", "Cut Size (Finished Product)"
        SHEET = "sheet", "Sheet Size (Press Sheet)"
        BOTH = "both", "Cut & Sheet"

    name = models.CharField(max_length=100, unique=True)
    width = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        help_text="Width in points (1 pt = 1/72 in)",
    )
    height = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        help_text="Height in points",
    )
    size_type = models.CharField(
        max_length=10,
        choices=SizeType.choices,
        default=SizeType.BOTH,
        help_text="Whether this size is used for cut sizes, sheet sizes, or both",
    )
    thumbnail = models.ImageField(
        upload_to="print_sizes/thumbnails/",
        blank=True,
        null=True,
        help_text="Optional preview image for this size (shown in upload UI)",
    )
    canva_template_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Canva template URL for this print size",
    )
    category = models.ForeignKey(
        "impose.ProductCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="print_sizes",
        help_text="Group this size under a product category (e.g. Postcards, Business Cards)",
    )
    is_published = models.BooleanField(
        default=True,
        help_text="Published sizes appear on the public Templates page.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Print Size"
        verbose_name_plural = "Print Sizes"

    def __str__(self):
        return self.name

    @property
    def label(self):
        """Human-readable dimensions, e.g. '3.5 × 2 in'."""
        w = round(float(self.width) / POINTS_PER_INCH, 4)
        h = round(float(self.height) / POINTS_PER_INCH, 4)
        return f"{w:g} × {h:g} in"

    @property
    def width_in(self):
        return round(float(self.width) / POINTS_PER_INCH, 4)

    @property
    def height_in(self):
        return round(float(self.height) / POINTS_PER_INCH, 4)


class ImpositionTemplate(models.Model):
    """Defines how pages should be imposed onto a press sheet."""

    name = models.CharField(max_length=100, unique=True)
    product_category = models.ForeignKey(
        "impose.ProductCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="imposition_templates",
        help_text="Product category from the lookup table (e.g. Bookmarks, Postcards)",
    )
    cut_size = models.ForeignKey(
        "impose.PrintSize",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="templates_cut",
        help_text="Named cut size (finished product dimensions) from the lookup table",
    )
    sheet_size = models.ForeignKey(
        "impose.PrintSize",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="templates_sheet",
        help_text="Named sheet size (press sheet dimensions) from the lookup table",
    )
    # Cut size — the finished (trimmed) product dimensions, excluding bleed
    cut_width = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Finished cut width in points (1 pt = 1/72 in)",
    )
    cut_height = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Finished cut height in points",
    )
    sheet_width = models.DecimalField(
        max_digits=8, decimal_places=3, help_text="Points (1 pt = 1/72 in)"
    )
    sheet_height = models.DecimalField(
        max_digits=8, decimal_places=3, help_text="Points"
    )
    bleed = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0,
        help_text="Bleed in points (uniform, all sides)",
    )
    margin_top = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    margin_right = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    margin_bottom = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    margin_left = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    barcode_x = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Barcode X position in points (left edge of barcode block, from left of sheet)",
    )
    barcode_y = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Barcode Y position in points (bottom edge of barcode block, from bottom of sheet)",
    )
    # DC-646 Code 39 barcode block size defaults: 1.25" × 0.35"
    barcode_width = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=90.0,  # 1.25" × 72 pt/in = 90 pt
        help_text='Code 39 barcode block width in points (DC-646 default: 90 pt = 1.25")',
    )
    barcode_height = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=25.2,  # 0.35" × 72 pt/in = 25.2 pt
        help_text='Code 39 barcode block height in points (DC-646 default: 25.2 pt = 0.35")',
    )
    columns = models.PositiveSmallIntegerField(default=1)
    rows = models.PositiveSmallIntegerField(default=1)
    print_barcode = models.BooleanField(
        default=True,
        help_text="Print the barcode overlay on this layout. Uncheck if the barcode position overlaps artwork (the barcode number will still appear in the filename sent to the Fiery).",
    )
    allow_mailmerge = models.BooleanField(
        default=False,
        help_text="Allow this template to be selected when creating a mail merge job.",
    )
    cutter_program = models.ForeignKey(
        "cutter.CutterProgram",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="imposition_templates",
        help_text="Barcode program to stamp on each sheet when imposing this template.",
    )
    routing_preset = models.ForeignKey(
        "routing.RoutingPreset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="imposition_templates",
        help_text="Printer preset to use when routing jobs with this template.",
    )
    notes = models.TextField(blank=True)
    is_published = models.BooleanField(
        default=True,
        help_text="Published templates are visible on the public Templates page.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Imposition Template"
        verbose_name_plural = "Imposition Templates"

    def __str__(self):
        return self.name

    def _to_in(self, pts):
        """Convert stored points value to inches."""
        if pts is None:
            return None
        return round(float(pts) / POINTS_PER_INCH, 4)

    @property
    def cut_width_in(self):
        return self._to_in(self.cut_width)

    @property
    def cut_height_in(self):
        return self._to_in(self.cut_height)

    @property
    def cut_size_label(self):
        """Human-readable cut size, e.g. '3.5 × 2 in'."""
        w = self._to_in(self.cut_width)
        h = self._to_in(self.cut_height)
        if w is not None and h is not None:
            return f"{w:g} × {h:g} in"
        return "—"

    @property
    def sheet_width_in(self):
        return self._to_in(self.sheet_width)

    @property
    def sheet_height_in(self):
        return self._to_in(self.sheet_height)

    @property
    def bleed_in(self):
        return self._to_in(self.bleed)

    @property
    def margin_top_in(self):
        return self._to_in(self.margin_top)

    @property
    def margin_right_in(self):
        return self._to_in(self.margin_right)

    @property
    def margin_bottom_in(self):
        return self._to_in(self.margin_bottom)

    @property
    def margin_left_in(self):
        return self._to_in(self.margin_left)

    @property
    def sheet_size_label(self):
        """Human-readable sheet size, e.g. '12.5 × 19 in'."""
        w = self._to_in(self.sheet_width)
        h = self._to_in(self.sheet_height)
        if w is not None and h is not None:
            return f"{w:g} × {h:g} in"
        return "—"

    def clean(self):
        """Validate that the cut-size grid fits within the sheet dimensions."""
        # Resolve scalar dimensions — fall back to FK sizes if scalars are not set yet
        # (e.g. when saving via the admin form that only exposes the PrintSize FKs).
        cut_w = self.cut_width
        cut_h = self.cut_height
        sheet_w = self.sheet_width
        sheet_h = self.sheet_height
        if (cut_w is None or cut_h is None) and self.cut_size_id:
            try:
                cs = PrintSize.objects.get(pk=self.cut_size_id)
                cut_w = cs.width
                cut_h = cs.height
            except PrintSize.DoesNotExist:
                pass
        if (sheet_w is None or sheet_h is None) and self.sheet_size_id:
            try:
                ss = PrintSize.objects.get(pk=self.sheet_size_id)
                sheet_w = ss.width
                sheet_h = ss.height
            except PrintSize.DoesNotExist:
                pass

        if cut_w is not None and cut_h is not None and sheet_w is not None and sheet_h is not None:
            bleed = float(self.bleed or 0)
            cell_w = float(cut_w) + 2 * bleed
            cell_h = float(cut_h) + 2 * bleed
            grid_w = self.columns * cell_w
            grid_h = self.rows * cell_h
            sw = float(sheet_w)
            sh = float(sheet_h)
            errors = {}
            if grid_w > sw:
                cw_in = round(cell_w / POINTS_PER_INCH, 4)
                sw_in = round(sw / POINTS_PER_INCH, 4)
                errors["columns"] = (
                    f"{self.columns} column(s) × {cw_in:g}\" cell = {self.columns * cw_in:g}\" "
                    f"exceeds sheet width {sw_in:g}\""
                )
            if grid_h > sh:
                ch_in = round(cell_h / POINTS_PER_INCH, 4)
                sh_in = round(sh / POINTS_PER_INCH, 4)
                errors["rows"] = (
                    f"{self.rows} row(s) × {ch_in:g}\" cell = {self.rows * ch_in:g}\" "
                    f"exceeds sheet height {sh_in:g}\""
                )
            if errors:
                raise ValidationError(errors)
