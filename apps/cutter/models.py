from django.db import models


class CutterProgram(models.Model):
    """Represents a DC-646 cutter program."""

    name = models.CharField(max_length=100, unique=True)
    duplo_code = models.CharField(max_length=50, help_text="Program ID/barcode value for the DC-646")
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Cutter Program"
        verbose_name_plural = "Cutter Programs"

    def __str__(self):
        return f"{self.name} ({self.duplo_code})"
