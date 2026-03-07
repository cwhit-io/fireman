import uuid

from django.db import models


class PrintJob(models.Model):
    """Represents a single print job from intake to delivery."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        IMPOSED = "imposed", "Imposed"
        ROUTING = "routing", "Routing"
        SENT = "sent", "Sent"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to="jobs/originals/")
    imposed_file = models.FileField(upload_to="jobs/imposed/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    page_width = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Points")
    page_height = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Points")
    product_type = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    imposition_template = models.ForeignKey(
        "impose.ImpositionTemplate",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )
    cutter_program = models.ForeignKey(
        "cutter.CutterProgram",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )
    routing_preset = models.ForeignKey(
        "routing.RoutingPreset",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Print Job"
        verbose_name_plural = "Print Jobs"

    def __str__(self):
        return self.name or str(self.id)

    @property
    def page_size_label(self):
        """Human-readable page size, e.g. '8.5 × 11 in'."""
        if self.page_width and self.page_height:
            w = float(self.page_width) / 72
            h = float(self.page_height) / 72
            return f"{w:.3g} × {h:.3g} in"
        return "—"
