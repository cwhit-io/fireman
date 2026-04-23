from django.db import models


class CostRate(models.Model):
    """
    Per-page cost rates used to calculate job costs.
    Only one active rate set is expected at a time.
    """

    label = models.CharField(max_length=100, default="Default")
    color_per_page = models.DecimalField(
        max_digits=8, decimal_places=4, default="0.0500",
        help_text="Cost per color page (one side)",
    )
    bw_per_page = models.DecimalField(
        max_digits=8, decimal_places=4, default="0.0100",
        help_text="Cost per black & white page (one side)",
    )
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cost Rate"
        verbose_name_plural = "Cost Rates"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.label} (color ${self.color_per_page} / bw ${self.bw_per_page})"


class PrintLog(models.Model):
    """
    A single print job entry pulled from the Fiery job log.
    Represents any user — not limited to Ember/Django users.
    """

    class ColorMode(models.TextChoices):
        COLOR = "color", "Color"
        BW = "bw", "Black & White"
        MIXED = "mixed", "Mixed"

    # --- Identity ---------------------------------------------------------
    fiery_job_id = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text="Job ID as reported by the Fiery",
    )
    username = models.CharField(
        max_length=255, db_index=True,
        help_text="Username as reported in the Fiery log (any user, not just Ember users)",
    )
    job_name = models.CharField(max_length=500, blank=True)

    # --- Timing -----------------------------------------------------------
    printed_at = models.DateTimeField(
        db_index=True,
        help_text="When the job completed on the Fiery",
    )
    imported_at = models.DateTimeField(auto_now_add=True)

    # --- Page counts ------------------------------------------------------
    color_pages = models.PositiveIntegerField(default=0)
    bw_pages = models.PositiveIntegerField(default=0)
    copies = models.PositiveSmallIntegerField(default=1)
    color_mode = models.CharField(
        max_length=10, choices=ColorMode.choices, default=ColorMode.COLOR,
    )

    # --- Media ------------------------------------------------------------
    media_size = models.CharField(max_length=100, blank=True)
    media_type = models.CharField(max_length=100, blank=True)
    duplex = models.BooleanField(default=False)

    # --- Cost -------------------------------------------------------------
    cost_rate = models.ForeignKey(
        CostRate, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="Rate snapshot used when cost was calculated",
    )
    calculated_cost = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Total cost of this job at the time of calculation",
    )

    # --- Raw --------------------------------------------------------------
    raw_data = models.JSONField(
        default=dict, blank=True,
        help_text="Full raw log entry from Fiery for reference",
    )

    class Meta:
        verbose_name = "Print Log Entry"
        verbose_name_plural = "Print Log"
        ordering = ["-printed_at"]
        indexes = [
            models.Index(fields=["username", "printed_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["fiery_job_id"],
                condition=models.Q(fiery_job_id__gt=""),
                name="unique_fiery_job_id_nonempty",
            )
        ]

    def __str__(self):
        return f"{self.username} — {self.job_name or 'untitled'} ({self.printed_at:%Y-%m-%d})"

    @property
    def total_impressions(self):
        return (self.color_pages + self.bw_pages) * self.copies

    def calculate_cost(self, rate: CostRate | None = None) -> None:
        """Compute and store the job cost using *rate* (or the active rate)."""
        if rate is None:
            rate = CostRate.objects.filter(active=True).order_by("-updated_at").first()
        if rate is None:
            return
        cost = (
            self.color_pages * self.copies * rate.color_per_page
            + self.bw_pages * self.copies * rate.bw_per_page
        )
        self.cost_rate = rate
        self.calculated_cost = cost
        self.save(update_fields=["cost_rate", "calculated_cost"])
