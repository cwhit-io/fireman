import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('impose', '0011_add_allow_mailmerge'),
        ('mailmerge', '0004_merge_0003_migrations'),
    ]

    operations = [
        migrations.AddField(
            model_name='mailmergejob',
            name='impose_template',
            field=models.ForeignKey(
                blank=True,
                help_text='Imposition template used for gang-up sheet generation.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mail_merge_jobs',
                to='impose.impositiontemplate',
            ),
        ),
    ]
