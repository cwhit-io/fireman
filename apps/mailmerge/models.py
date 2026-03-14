import uuid

from django.conf import settings
from django.db import models


class MailMergeJob(models.Model):
    """Represents a USPS Intelligent Mail postcard mail-merge job."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True)
    artwork_file = models.FileField(
        upload_to="mailmerge/artwork/",
        help_text="Postcard artwork PDF (1 or 2 pages — front and/or address side).",
    )
    csv_file = models.FileField(
        upload_to="mailmerge/csv/",
        help_text="USPS Intelligent Mail CSV with address and IMb data.",
    )
    output_file = models.FileField(
        upload_to="mailmerge/output/",
        blank=True,
        null=True,
        help_text="Generated mail-merged PDF (one page per recipient).",
    )
    gangup_file = models.FileField(
        upload_to="mailmerge/output/",
        blank=True,
        null=True,
        help_text="Artwork gang-up PDF (N-up press sheet, for use as Fiery master).",
    )
    address_pdf_file = models.FileField(
        upload_to="mailmerge/output/",
        blank=True,
        null=True,
        help_text="Address step-and-repeat PDF (one sheet per N records).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    record_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of address records in the CSV.",
    )
    # ── Artwork metadata ──────────────────────────────────────────────────
    artwork_page_count = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Number of pages detected in the uploaded artwork PDF.",
    )
    # ── Card size (in points) ─────────────────────────────────────────────
    card_width = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Finished card width in PDF points (derived from artwork page).",
    )
    card_height = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Finished card height in PDF points.",
    )
    # ── Address block settings ────────────────────────────────────────────
    merge_page = models.PositiveSmallIntegerField(
        default=1,
        help_text="1-based index of the artwork page that receives the address block.",
    )
    addr_x_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Address block left edge, in inches from the left of the card. "
        "Defaults to card_width - 4.5 in when blank.",
    )
    addr_y_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Address block bottom edge, in inches from the bottom of the card. "
        "Defaults to 2.5 in when blank.",
    )
    # ── Gang-up grid ─────────────────────────────────────────────────────
    gangup_cols = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Number of columns in the artwork gang-up grid.",
    )
    gangup_rows = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Number of rows in the artwork gang-up grid.",
    )
    impose_template = models.ForeignKey(
        "impose.ImpositionTemplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mail_merge_jobs",
        help_text="Imposition template used for gang-up sheet generation.",
    )
    error_message = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mail_merge_jobs",
        help_text="User who created this mail merge job.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mail Merge Job"
        verbose_name_plural = "Mail Merge Jobs"

    def __str__(self):
        return self.name or str(self.id)


FONT_CHOICES = [
    ("Helvetica", "Helvetica"),
    ("Helvetica-Bold", "Helvetica Bold"),
    ("Helvetica-Oblique", "Helvetica Italic"),
    ("Helvetica-BoldOblique", "Helvetica Bold Italic"),
    ("Times-Roman", "Times Roman"),
    ("Times-Bold", "Times Bold"),
    ("Courier", "Courier"),
    ("Courier-Bold", "Courier Bold"),
]

DEFAULT_CSV_FIELDS = [
    "encodedimbno",  # bottom — rendered as USPS IMb visual barcode
    "city-state-zip",
    "primary street",
    "sec-primary street",
    "urbanization",
    "company",
    "name",
    "presorttrayid",  # top
]


class AddressBlockConfig(models.Model):
    """Singleton model storing the site-wide default address block position.

    Always access via ``AddressBlockConfig.get_solo()``.
    The x position can be expressed as an absolute left-edge value OR as a
    distance from the right edge of the card (``from_right_in``).  The latter
    generally produces more predictable results as it directly matches the USPS
    address-placement requirement (≥1" from right edge).
    """

    # Preview / default card dimensions used on the config page itself
    preview_card_width_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=6.0,
        help_text="Card width used in the preview on the defaults page (inches).",
    )
    preview_card_height_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=9.0,
        help_text="Card height used in the preview on the defaults page (inches).",
    )

    # Default address position – mirrors MailMergeJob.addr_x_in / addr_y_in
    addr_x_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Default left edge of address block in inches from card left. "
            'Leave blank to use card_width − 4.5".'
        ),
    )
    addr_y_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Default bottom edge of address block in inches from card bottom. "
            'Leave blank to use 2.5".'
        ),
    )

    # ── Typography ────────────────────────────────────────────────────────
    font_name = models.CharField(
        max_length=60,
        choices=FONT_CHOICES,
        default="Helvetica",
        help_text="PDF Type1 built-in font for address text.",
    )
    font_size = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=9.0,
        help_text="Address text font size in points.",
    )
    line_height = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=13.0,
        help_text="Vertical spacing between address lines in points.",
    )

    # ── Address box size ──────────────────────────────────────────────────
    addr_block_width_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=4.25,
        help_text="Width of the address block in inches (for preview only).",
    )

    # ── CSV field selection / ordering ────────────────────────────────────
    csv_fields = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Ordered list of CSV column keys to include in the address block "
            "(bottom-to-top). Leave empty to use all default USPS fields."
        ),
    )

    # ── Barcode (encodedimbno) ────────────────────────────────────────────
    barcode_font_size = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=14.0,
        help_text=(
            "Point size for the USPS IMb barcode line (encodedimbno field). "
            "14pt renders the barcode at USPS-spec dimensions."
        ),
    )
    barcode_x_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Left edge of the IMb barcode from card left (inches). "
            "Leave blank to use the main address block X position."
        ),
    )
    barcode_y_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Bottom baseline of the IMb barcode from card bottom (inches). "
            "Leave blank to use the main address block Y position."
        ),
    )

    # ── Tray ID (presorttrayid) ───────────────────────────────────────────
    tray_x_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Left edge of the presort tray ID from card left (inches). "
            "Leave blank to include tray ID in the normal address block flow."
        ),
    )
    tray_y_in = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Bottom baseline of the presort tray ID from card bottom (inches). "
            "Leave blank to include tray ID in the normal address block flow."
        ),
    )
    tray_font_size = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Font size for the tray ID text (points). "
            "Leave blank to use the main address font size."
        ),
    )

    class Meta:
        verbose_name = "Address Block Config"
        verbose_name_plural = "Address Block Config"

    def __str__(self):
        return "Address Block Defaults"

    @classmethod
    def get_solo(cls):
        """Return the single config row, creating it with defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
