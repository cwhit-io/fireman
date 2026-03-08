"""
One-time management command to seed the CutterProgram table with the
60 standard Duplo DC-646 programs.

Usage:
    python manage.py seed_cutter_programs
    python manage.py seed_cutter_programs --overwrite   # update names if duplo_code already exists
"""

from django.core.management.base import BaseCommand

PROGRAMS = [
    ("001", "QTR-8.5x11P-N"),
    ("002", "HLF-8.5X11L-N"),
    ("003", "BIZ Card"),
    ("004", "Thank You Cards"),
    ("005", "Qtr Bleed"),
    ("006", "Half Page Bleed"),
    ("007", "8.5x11 Bleed"),
    ("008", "11x17 Bleed"),
    ("009", "4x6 Bleed"),
    ("010", "Ticket No PERF"),
    ("011", "Ticket 6x2"),
    ("012", "DOORHNG-12x18"),
    ("013", "TBLTENT-12x18"),
    ("014", "Crease Tri Fold"),
    ("015", "Crease Half"),
    ("016", "MemberBallot"),
    ("017", "Give Light"),
    ("018", "Next Steps 2022"),
    ("019", "Small-Notepad"),
    ("020", "5x7 Bleed"),
    ("021", "11x17-Half"),
    ("022", "Large Notepad"),
    ("023", "2.5 x 7.5 Bookmark"),
    ("024", "5.5x8.5"),
    ("025", "Temp-D"),
    ("026", "5.5 Square"),
    ("027", "Give Light 2022"),
    ("028", "2x5.5 Bookmark"),
    ("029", "Bulletin"),
    ("030", "BookmarkLG"),
    ("031", "1319connect"),
    ("032", "13x19-12x18"),
    ("033", "Parking Pass"),
    ("034", "8X5.25"),
    ("035", "4.25x5.5 Bleed"),
    ("036", "NameTag"),
    ("037", "Bookmark Step 1"),
    ("038", "Bookmark Step 2"),
    ("039", "4in Square"),
    ("040", "Crease Half - Booklet Cover"),
    ("041", "Booklet Cover Bleed"),
    ("042", "4x6"),
    ("043", "Half-Page-Canva"),
    ("044", "Poster-Canva"),
    ("045", "11.5x16.5"),
    ("046", "13x19 BMark 2x6"),
    ("047", "erASSTER iNVITE"),
    ("048", "Name Plate"),
    ("049", "13x19 ThankYou"),
    ("050", "communion"),
    ("051", "Cube"),
    ("052", "Bookmark 2.5x6"),
    ("053", "A6 Bleed"),
    ("054", "TBLTENT-8.5x11"),
    ("055", "3.5 x 8.5 Bookmark"),
    ("056", "Wide Card"),
    ("057", "6x9"),
    ("058", "Trading Cards"),
    ("059", "9in card-crese"),
    ("060", "Brochure Crease"),
]


class Command(BaseCommand):
    help = "Seed the CutterProgram table with the standard DC-646 programs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Update the name of existing programs (matched by duplo_code).",
        )

    def handle(self, *args, **options):
        from apps.cutter.models import CutterProgram

        overwrite = options["overwrite"]
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for code, name in PROGRAMS:
            obj, created = CutterProgram.objects.get_or_create(
                duplo_code=code,
                defaults={"name": name, "active": True},
            )
            if created:
                created_count += 1
                self.stdout.write(f"  Created  [{code}] {name}")
            elif overwrite and obj.name != name:
                obj.name = name
                obj.save(update_fields=["name"])
                updated_count += 1
                self.stdout.write(f"  Updated  [{code}] {name}")
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {created_count} created, {updated_count} updated, {skipped_count} skipped."
            )
        )
