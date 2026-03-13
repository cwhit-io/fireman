from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('impose', '0010_remove_layout_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='impositiontemplate',
            name='allow_mailmerge',
            field=models.BooleanField(
                default=False,
                help_text='Allow this template to be selected when creating a mail merge job.',
            ),
        ),
    ]
