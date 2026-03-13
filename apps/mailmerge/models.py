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
        help_text="Postcard artwork PDF (one page = one card design).",
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
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mail Merge Job"
        verbose_name_plural = "Mail Merge Jobs"

    def __str__(self):
        return self.name or str(self.id)
