from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('impose', '0009_remove_category_simplify_layout_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='impositiontemplate',
            name='layout_type',
        ),
    ]
