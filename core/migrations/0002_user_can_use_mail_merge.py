from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_use_mail_merge",
            field=models.BooleanField(
                default=False,
                help_text="Allow this user to access the Mail Merge feature.",
            ),
        ),
    ]
