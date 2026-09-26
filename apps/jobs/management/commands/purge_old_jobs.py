"""Management command to delete print jobs older than 30 days that are not saved."""

from django.core.management.base import BaseCommand

from apps.jobs.services import purge_unsaved_jobs


class Command(BaseCommand):
    help = "Delete print jobs older than 30 days that have not been marked as saved."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days after which unsaved jobs are deleted (default: 30)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview which jobs would be deleted without actually deleting them",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        result = purge_unsaved_jobs(days=days, dry_run=dry_run)
        count = result["count"]
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: {count} job(s) would be deleted "
                    f"(older than {days} days, not saved)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {result['deleted']} job(s) older than {days} days "
                    "that were not saved."
                )
            )
