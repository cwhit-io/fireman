import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mailmerge", "0002_add_card_size_and_address_position"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="mailmergejob",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                help_text="User who created this mail merge job.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mail_merge_jobs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
