from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0006_add_owner_and_is_global"),
    ]

    operations = [
        migrations.AddField(
            model_name="printjob",
            name="thumbnail",
            field=models.ImageField(
                blank=True,
                help_text="Small JPEG of the first page, used in the job list.",
                null=True,
                upload_to="jobs/thumbnails/",
            ),
        ),
    ]
