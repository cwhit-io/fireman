from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.jobs.models import PrintJob


@receiver(post_delete, sender=PrintJob)
def delete_job_files_on_delete(sender, instance, **kwargs):
    """Remove associated uploaded files from storage when a PrintJob is deleted.

    Uses the FieldFile.delete(save=False) API so storage backends are respected.
    """
    for field_name in ("file", "imposed_file", "thumbnail"):
        try:
            f = getattr(instance, field_name, None)
            if f and getattr(f, "name", None):
                f.delete(save=False)
        except Exception:
            # Don't raise from signal handlers
            pass
