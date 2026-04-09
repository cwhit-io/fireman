"""Management command to delete temp QR logo files older than a configurable age."""
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete temporary QR logo uploads older than --max-age-hours (default: 24)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-hours",
            type=float,
            default=24.0,
            help="Delete files older than this many hours (default: 24).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print files that would be deleted without actually deleting them.",
        )

    def handle(self, *args, **options):
        max_age_seconds = options["max_age_hours"] * 3600
        dry_run = options["dry_run"]
        cutoff = time.time() - max_age_seconds

        temp_dir = os.path.join(settings.MEDIA_ROOT, "temp_logos")
        if not os.path.isdir(temp_dir):
            self.stdout.write("temp_logos directory does not exist — nothing to clean.")
            return

        deleted = 0
        errors = 0
        for filename in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff:
                    if dry_run:
                        self.stdout.write(f"[dry-run] Would delete: {filepath}")
                    else:
                        os.remove(filepath)
                        deleted += 1
            except OSError as exc:
                self.stderr.write(f"Error processing {filepath}: {exc}")
                errors += 1

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — no files deleted."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted} file(s). Errors: {errors}.")
            )
