import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0005_add_preflight_images"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="printjob",
            name="is_global",
            field=models.BooleanField(
                default=False,
                help_text="Saved job visible to all users (admin-controlled). Only applies when is_saved=True.",
            ),
        ),
        migrations.AddField(
            model_name="printjob",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                help_text="User who uploaded this job.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="print_jobs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
