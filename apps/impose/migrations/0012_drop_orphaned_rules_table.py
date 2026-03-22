"""
Drop the orphaned `rules_rule` table left behind after the `rules` app was
removed from INSTALLED_APPS. The migration records for that app are also
cleaned up so Django's migration state stays consistent.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("impose", "0011_add_allow_mailmerge"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DROP TABLE IF EXISTS "rules_rule";
                DELETE FROM django_migrations WHERE app = 'rules';
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
