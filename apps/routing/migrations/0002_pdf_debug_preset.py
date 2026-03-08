from django.db import migrations

def create_pdf_debug_preset(apps, schema_editor):
    RoutingPreset = apps.get_model('routing', 'RoutingPreset')
    if not RoutingPreset.objects.filter(name="Print to PDF (Debug)").exists():
        RoutingPreset.objects.create(
            name="Print to PDF (Debug)",
            printer_queue="PDF",
            media_type="",
            media_size="",
            duplex="simplex",
            color_mode="color",
            tray="",
            copies=1,
            extra_lpr_options="",
            active=True,
        )

class Migration(migrations.Migration):
    dependencies = [
        ("routing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_pdf_debug_preset),
    ]
