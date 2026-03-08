from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("routing", "0002_pdf_debug_preset"),
    ]

    operations = [
        migrations.AddField(
            model_name="routingpreset",
            name="fiery_options",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Fiery PPD options sent as -o key=value pairs",
            ),
        ),
    ]
