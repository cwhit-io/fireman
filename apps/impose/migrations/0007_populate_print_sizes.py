"""
Data migration: seed PrintSize records for all cut sizes and sheet sizes
that are already present on ImpositionTemplate rows, then back-fill the
cut_size / sheet_size FK fields on every template.
"""

from django.db import migrations
from decimal import Decimal


# (name, width_pt, height_pt, size_type)
CUT_SIZES = [
    ("3.5 × 2 in",      Decimal("252.000"), Decimal("144.000"), "cut"),
    ("3.5 × 2.5 in",    Decimal("252.000"), Decimal("180.000"), "cut"),
    ("3.5 × 3.5 in",    Decimal("252.000"), Decimal("252.000"), "cut"),
    ("3.5 × 4 in",      Decimal("252.000"), Decimal("288.000"), "cut"),
    ("3.5 × 5 in",      Decimal("252.000"), Decimal("360.000"), "cut"),
    ("3.5 × 8.5 in",    Decimal("252.000"), Decimal("612.000"), "cut"),
    ("4 × 4 in",        Decimal("288.000"), Decimal("288.000"), "cut"),
    ("5.25 × 8 in",     Decimal("378.000"), Decimal("576.000"), "cut"),
    ("5.5 × 4 in",      Decimal("396.000"), Decimal("288.000"), "cut"),
    ("5.5 × 4.25 in",   Decimal("396.000"), Decimal("306.000"), "cut"),
    ("5.5 × 8.5 in",    Decimal("396.000"), Decimal("612.000"), "cut"),
    ("6 × 2.5 in",      Decimal("432.000"), Decimal("180.000"), "cut"),
    ("6 × 4 in",        Decimal("432.000"), Decimal("288.000"), "cut"),
    ("6 × 8.75 in",     Decimal("432.000"), Decimal("630.000"), "cut"),
    ("8.5 × 8.5 in",    Decimal("612.000"), Decimal("612.000"), "cut"),
    ("11 × 17 in",      Decimal("792.000"), Decimal("1224.000"), "cut"),
    ("11.5 × 16.5 in",  Decimal("828.000"), Decimal("1188.000"), "cut"),
    ("11.5 × 17.5 in",  Decimal("828.000"), Decimal("1260.000"), "cut"),
]

SHEET_SIZES = [
    ("12 × 18 in", Decimal("864.000"),  Decimal("1296.000"), "sheet"),
    ("13 × 19 in", Decimal("936.000"),  Decimal("1368.000"), "sheet"),
]


def forwards(apps, schema_editor):
    PrintSize = apps.get_model("impose", "PrintSize")
    ImpositionTemplate = apps.get_model("impose", "ImpositionTemplate")

    # --- 1. Create PrintSize records (skip if already exists by name) ---
    for name, width, height, size_type in CUT_SIZES + SHEET_SIZES:
        PrintSize.objects.get_or_create(
            name=name,
            defaults={"width": width, "height": height, "size_type": size_type},
        )

    # --- 2. Build lookup: (width_pt, height_pt) -> PrintSize instance ---
    cut_lookup = {
        (ps.width, ps.height): ps
        for ps in PrintSize.objects.filter(size_type="cut")
    }
    sheet_lookup = {
        (ps.width, ps.height): ps
        for ps in PrintSize.objects.filter(size_type="sheet")
    }

    # --- 3. Back-fill FKs on every ImpositionTemplate ---
    for template in ImpositionTemplate.objects.all():
        changed = False

        if template.cut_width and template.cut_height:
            key = (template.cut_width, template.cut_height)
            ps = cut_lookup.get(key)
            if ps and template.cut_size_id != ps.pk:
                template.cut_size = ps
                changed = True

        key = (template.sheet_width, template.sheet_height)
        ps = sheet_lookup.get(key)
        if ps and template.sheet_size_id != ps.pk:
            template.sheet_size = ps
            changed = True

        if changed:
            template.save(update_fields=["cut_size", "sheet_size"])


def backwards(apps, schema_editor):
    PrintSize = apps.get_model("impose", "PrintSize")
    ImpositionTemplate = apps.get_model("impose", "ImpositionTemplate")

    # Clear the FK fields first, then delete the seeded sizes
    ImpositionTemplate.objects.all().update(cut_size=None, sheet_size=None)

    names = {name for name, *_ in CUT_SIZES + SHEET_SIZES}
    PrintSize.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("impose", "0006_add_print_size_product_category"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
