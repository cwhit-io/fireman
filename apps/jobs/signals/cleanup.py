import os

from django.conf import settings
from django.db.models.signals import post_save
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
    imposed_dir = os.path.join(settings.MEDIA_ROOT, "jobs/imposed")
    if not os.path.isdir(imposed_dir):
        return
    for fname in os.listdir(imposed_dir):
        rel_path = f"jobs/imposed/{fname}"
        if rel_path not in referenced:
            try:
                os.remove(os.path.join(imposed_dir, fname))
            except Exception:
                pass
