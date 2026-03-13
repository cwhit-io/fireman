import uuid

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
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mail Merge Job"
        verbose_name_plural = "Mail Merge Jobs"

    def __str__(self):
        return self.name or str(self.id)
