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
    category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional category for grouping templates (e.g. 'Business Cards', 'Postcards')",
    )
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
    layout_type = models.CharField(
        max_length=20, choices=LayoutType.choices, blank=True, default="custom"
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
