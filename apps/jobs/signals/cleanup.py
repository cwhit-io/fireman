import os

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.jobs.models import PrintJob


@receiver(post_save, sender=PrintJob)
def cleanup_unreferenced_imposed_files(sender, instance, **kwargs):
    # Get all imposed_file paths referenced in the DB
    referenced = set(
        PrintJob.objects.exclude(imposed_file="")
        .exclude(imposed_file=None)
        .values_list("imposed_file", flat=True)
    )
    # Clean both imposed and original uploaded files that are no longer referenced
    targets = [
        ("jobs/imposed", referenced),
        (
            "jobs/originals",
            set(
                PrintJob.objects.exclude(file="")
                .exclude(file=None)
                .values_list("file", flat=True)
            ),
        ),
    ]

    for rel_dir, referenced_set in targets:
        full_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
        if not os.path.isdir(full_dir):
            continue
        for fname in os.listdir(full_dir):
            rel_path = f"{rel_dir}/{fname}"
            if rel_path not in referenced_set:
                try:
                    os.remove(os.path.join(full_dir, fname))
                except Exception:
                    # Silently ignore errors to avoid breaking signal handlers
                    pass


@receiver(post_delete, sender=PrintJob)
def delete_job_files_on_delete(sender, instance, **kwargs):
    """Remove associated uploaded files from storage when a PrintJob is deleted.

    Uses the FieldFile.delete(save=False) API so storage backends are respected.
    """
    for field_name in ("file", "imposed_file"):
        try:
            f = getattr(instance, field_name, None)
            if f and getattr(f, "name", None):
                # delete file from storage without saving model
                f.delete(save=False)
        except Exception:
            # Don't raise from signal handlers
            pass
