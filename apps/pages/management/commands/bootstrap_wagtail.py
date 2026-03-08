"""
Bootstrap the Wagtail site with an initial HomePage.

Safe to run multiple times — skips creation if already set up.

Usage:
    python manage.py bootstrap_wagtail
    make wagtail-init
"""

from django.core.management.base import BaseCommand
from wagtail.models import Page

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
                    """
                    Legacy Wagtail bootstrap command. No longer used.
                    """
            Page.fix_tree()
