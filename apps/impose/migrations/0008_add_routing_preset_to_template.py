from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("impose", "0007_populate_print_sizes"),
        ("routing", "0004_alter_routingpreset_extra_lpr_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="impositiontemplate",
            name="routing_preset",
            field=models.ForeignKey(
                blank=True,
                help_text="Printer preset to use when routing jobs with this template.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="imposition_templates",
                to="routing.routingpreset",
            ),
        ),
    ]
