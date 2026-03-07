"""
Bootstrap the Wagtail site with an initial HomePage.

Safe to run multiple times — skips creation if already set up.

Usage:
    python manage.py bootstrap_wagtail
    make wagtail-init
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from apps.pages.models import HomePage


class Command(BaseCommand):
    help = "Create the default Wagtail Site and HomePage if they don't exist."

    def handle(self, *args, **options):
        # Wagtail ships with a default root Page (pk=1) and a "Welcome to Wagtail"
        # page (pk=2). We replace the welcome page with our HomePage.
        root_page = Page.objects.filter(depth=1).first()

        if not root_page:
            self.stderr.write("Root page not found — has migrate been run?")
            return

        if HomePage.objects.exists():
            self.stdout.write(self.style.WARNING("HomePage already exists, skipping."))
        else:
            # Remove the default "Welcome to Wagtail" page using Wagtail's delete
            # so treebeard child counters stay consistent
            for child in root_page.get_children():
                if not isinstance(child.specific, HomePage):
                    child.delete()

            # Rebuild tree paths/counts after deletion
            Page.fix_tree()
            root_page = Page.objects.filter(depth=1).first()

            home = HomePage(
                title="Home",
                slug="home",
                intro="<p>Welcome. Edit this page in the Wagtail admin at <b>/cms/</b>.</p>",
            )
            root_page.add_child(instance=home)
            home.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"Created HomePage (pk={home.pk})."))

        home = HomePage.objects.first()

        port = int(os.environ.get("PORT", 8085))
        site, created = Site.objects.update_or_create(
            is_default_site=True,
            defaults={
                "hostname": "localhost",
                "port": port,
                "site_name": settings.WAGTAIL_SITE_NAME,
                "root_page": home,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created default Wagtail Site."))
        else:
            self.stdout.write(self.style.SUCCESS("Updated default Wagtail Site."))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Visit http://localhost:{port}/ to see your homepage."
            )
        )
