# Canonical definition of the USPS Intelligent Mail presort CSV column schema.
#
# This file has zero dependencies so it can be imported by both Django code
# and standalone scripts (pco-pull.py, get_addresses.py) without requiring
# Django to be configured.
#
# All code that reads or writes presort CSVs should import from here rather
# than defining its own copy.

CSV_HEADERS = [
    "no",
    "name",
    "contactid",
    "company",
    "urbanization",
    "sec-primary street",
    "primary street",
    "city-state-zip",
    "ase",
    "oel",
    "presorttrayid",
    "presortdate",
    "imbno",
    "encodedimbno",
    "primary city",
    "primary state",
    "primary zip",
]
