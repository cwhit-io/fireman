from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cutter", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cutterprogram",
            name="barcode_x",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text="Barcode left edge on the sheet, in points (leave blank to use template default)",
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cutterprogram",
            name="barcode_y",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text="Barcode bottom edge on the sheet, in points (leave blank to use template default)",
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cutterprogram",
            name="barcode_width",
            field=models.DecimalField(
                decimal_places=3,
                default=90.0,
                help_text='Barcode block width in points (default 90 pt = 1.25")',
                max_digits=8,
            ),
        ),
        migrations.AddField(
            model_name="cutterprogram",
            name="barcode_height",
            field=models.DecimalField(
                decimal_places=3,
                default=25.2,
                help_text='Barcode block height in points (default 25.2 pt = 0.35")',
                max_digits=8,
            ),
        ),
    ]
