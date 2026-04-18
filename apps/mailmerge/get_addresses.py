"""Allen County sales extractor — core functionality.

This module provides:
- get_sales_data(month, year) -> list of records
- records_to_csv_bytes(records) -> bytes (CSV)
- save_to_csv(records, filename)
- generate_csv_for_period(month, year) -> (filename, bytes)

The module can be used from the CLI or imported by the Flask app.
"""

from __future__ import annotations

import calendar
import csv
import io
import re
import requests
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

from apps.mailmerge._csv_headers import CSV_HEADERS

API_BASE_URL = (
    "https://gis1.acimap.us/imapweb/rest/services/COMPS/Parcels_Sales_Live/MapServer/0/query"
)
FIELDS = [
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.PropAddress",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.City",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.ZipCode",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.SaleDate",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer1Name",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer2Name",
]

FIELD_MAP = {
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.PropAddress": "Property Address",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.City": "City",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.ZipCode": "ZIP Code",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.SaleDate": "Sale Date",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer1Name": "Buyer 1",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer2Name": "Buyer 2",
}

# ---------------------------------------------------------------------------
# Org detection — two-tier approach to minimize false positives on surnames
# ---------------------------------------------------------------------------

# Unambiguous substrings: safe to match anywhere in the string
_ORG_SUBSTRING_INDICATORS = [
    'LLC', 'L.L.C', 'INC', 'CORP', 'CO.', 'COMPANY', 'TRUST', 'BANK',
    'ASSOCIATES', 'HOLDINGS', 'LP', 'L.P.', 'LLP', 'L.L.P', 'PLLC',
    'P.L.L.C', 'C/O', 'PARTNERSHIP', 'PARTNERS', 'REALTY', 'REALTORS',
    'PROPERTIES', 'PROPERTY', 'INVESTMENTS', 'INVESTMENT', 'VENTURES',
    'VENTURE', 'DEVELOPMENT', 'DEVELOPERS', 'ACQUISITIONS', 'CONSTRUCTION',
    'REAL ESTATE', 'MANAGEMENT', 'ENTERPRISES', 'MORTGAGE', 'FINANCIAL',
    'AUTHORITY', 'COMMISSION', 'CITY OF', 'STATE OF', 'DEPARTMENT',
    'HABITAT', 'CHURCH', 'AKA', 'A.K.A', 'ALSO KNOWN', 'IRREVOCABLE',
    'REVOCABLE', 'LIVING TRUST', 'ESTATE OF', 'HEIRS OF',
]

# Ambiguous short words: only match on whole-word boundaries to avoid
# false-positiving on surnames (e.g. "JOHN LAND", "SARAH HOMES").
# Note: LAND is intentionally excluded — too common as a surname.
_ORG_WHOLE_WORD_INDICATORS = {
    'CO', 'GROUP', 'FUND', 'HOMES', 'HOUSING', 'CAPITAL', 'ASSETS',
    'SERVICES', 'SOLUTIONS', 'BUILDERS', 'FUNDING', 'COUNTY',
}


def _is_organization_name(name: str) -> bool:
    """Return True if the name appears to be a business, trust, or entity.

    Uses substring matching for unambiguous terms and whole-word matching
    for short/common words that could also be surnames.
    """
    if not name:
        return False
    n = name.upper()

    if any(ind in n for ind in _ORG_SUBSTRING_INDICATORS):
        return True

    tokens = set(re.findall(r'\b\w+\b', n))
    if tokens & _ORG_WHOLE_WORD_INDICATORS:
        return True

    return False


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _to_date_str(month: int, day: int, year: int) -> str:
    """Convert a date to YYYY-MM-DD format for SQL queries.

    The ArcGIS REST API requires DATE literals in the where clause when
    comparing date fields using CAST.
    """
    return f"{year:04d}-{month:02d}-{day:02d}"


def convert_timestamp(timestamp_ms: Optional[int]) -> str:
    """Convert epoch milliseconds to YYYY-MM-DD (returns empty string for falsy input)."""
    if not timestamp_ms:
        return ""
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# API fetch
# ---------------------------------------------------------------------------

def get_sales_data(month: int, year: int, batch_size: int = 1000) -> List[Dict[str, Any]]:
    """Fetch residential sales records from the GIS API for the given month/year.

    Paginates automatically using resultOffset until all records are retrieved.
    Returns the raw feature list (may be empty).
    """
    if month == 12:
        end_month, end_year = 1, year + 1
    else:
        end_month, end_year = month + 1, year

    start_date = _to_date_str(month, 1, year)
    end_date   = _to_date_str(end_month, 1, end_year)

    where_clause = (
        "GISPublished.sde.AssessorSalesBuildingsParcelInfo.Valid = 1 "
        "AND (GISPublished.sde.AssessorSalesBuildingsParcelInfo.ClassGroupDescription = 'Res Unimproved' "
        "OR GISPublished.sde.AssessorSalesBuildingsParcelInfo.ClassGroupDescription = 'Res Improved') "
        f"AND CAST(GISPublished.sde.AssessorSalesBuildingsParcelInfo.SaleDate AS DATE) >= DATE '{start_date}' "
        f"AND CAST(GISPublished.sde.AssessorSalesBuildingsParcelInfo.SaleDate AS DATE) < DATE '{end_date}'"
    )

    all_records: List[Dict[str, Any]] = []
    offset = 0

    while True:
        params = {
            "f": "json",
            "where": where_clause,
            "outFields": ",".join(FIELDS),
            "returnGeometry": "false",
            "orderByFields": "GISPublished.sde.AssessorSalesBuildingsParcelInfo.SaleDate DESC",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
        }
        headers = {"referer": "https://www.acimap.us/"}

        resp = requests.get(API_BASE_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features") or []
        if not features:
            break

        all_records.extend(features)
        if len(features) < batch_size:
            break

        offset += batch_size

    return all_records


# ---------------------------------------------------------------------------
# Name formatting
# ---------------------------------------------------------------------------

def _strip_initials(name: str) -> str:
    """Remove standalone initials, suffixes, and legal notations from a name.

    Strips:
    - Initials with periods:      'MASON S. & SOPHIA E. LINGG' -> 'MASON & SOPHIA LINGG'
    - Bare single-letter initials (not the first token):
                                  'CAROL J ROBERTS' -> 'CAROL ROBERTS'
                                  'GENE R'          -> 'GENE'
    - Name suffixes at end:       'WALKER, JR' -> 'WALKER', 'HILL III' -> 'HILL'
    - Power-of-attorney notation: 'SVOBODA BY AYRIKA PIER, AIF' -> 'SVOBODA'
    """
    s = name
    # Strip "X." initials (letter + period)
    s = re.sub(r'\b[A-Z]\.\s*', '', s)
    # Strip bare single-letter initials that are NOT the first token.
    # Lookbehind requires exactly one word-char + one space before the letter,
    # which ensures the initial is not the start of the string.
    s = re.sub(r'(?<=\w )[A-Z](?= |\Z)', '', s)
    # Strip name suffixes (Jr/Sr/II/III/IV) with optional preceding comma
    s = re.sub(r',?\s*\b(JR|SR|II|III|IV)\b\.?\s*$', '', s, flags=re.IGNORECASE)
    # Strip power-of-attorney / representative notation ("NAME BY AGENT, AIF")
    s = re.sub(r'\s+BY\s+.+$', '', s, flags=re.IGNORECASE)
    return ' '.join(s.split())


def _split_person_name(name: str) -> tuple[str, str]:
    """Return (given-part, last-name) for a likely person name.

    Handles "Last, First" and strips common suffixes (Jr, Sr, II, III, IV).
    """
    if not name:
        return '', ''
    s = ' '.join(name.replace(',', ' ').split())
    parts = s.split()
    suffixes = {'JR', 'SR', 'II', 'III', 'IV'}
    if parts and parts[-1].upper().replace('.', '') in suffixes:
        parts = parts[:-1]
    if len(parts) == 1:
        return parts[0], ''
    last = parts[-1]
    given = ' '.join(parts[:-1])
    return given, last


def format_recipient(buyer1: str | None, buyer2: str | None) -> str:
    """Return a single recipient string combining buyer1 and buyer2 intelligently.

    - Both people, same last name  -> "Given1 & Given2 Last"
    - Last-name-first (shared first word): "WENZEL JONATHAN & WENZEL SARAH"
                                       ->  "JONATHAN & SARAH WENZEL"
    - Both people, different names -> "Full1 & Full2"
    - Either is an org/entity      -> "Name1 & Name2" (no parsing)
    - Only one name present        -> that name as-is
    """
    b1 = _strip_initials((buyer1 or '').strip())
    b2 = _strip_initials((buyer2 or '').strip())

    if not b1 and not b2:
        return ''
    if not b1:
        return b2
    if not b2:
        return b1

    if _is_organization_name(b1) or _is_organization_name(b2):
        return f"{b1} & {b2}"

    # Last-name-first detection: both names share the same leading word
    # e.g. "WENZEL JONATHAN" & "WENZEL SARAH" → "JONATHAN & SARAH WENZEL"
    t1, t2 = b1.split(), b2.split()
    if len(t1) >= 2 and len(t2) >= 2 and t1[0].lower() == t2[0].lower():
        shared_last = t1[0]
        return f"{' '.join(t1[1:])} & {' '.join(t2[1:])} {shared_last}"

    g1, l1 = _split_person_name(b1)
    g2, l2 = _split_person_name(b2)

    if l1 and l2 and l1.lower() == l2.lower():
        return f"{g1} & {g2} {l1}"

    return f"{b1} & {b2}"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------

def _build_city_state_zip(city: str, state: str, zip_code: str) -> str:
    """Format the combined city-state-zip field, e.g. 'FORT WAYNE IN 46801'."""
    parts = [p for p in [city, state, zip_code] if p]
    return " ".join(parts)


def records_to_csv_bytes(
    records: List[Dict[str, Any]],
    skip_org_buyers: bool = True,
) -> bytes:
    """Serialize API records to the mail presort CSV format and return UTF-8 bytes.

    Populated columns:  name, primary street, city-state-zip,
                        primary city, primary state, primary zip
    Blank columns:      no, contactid, company, urbanization,
                        sec-primary street, ase, oel, presorttrayid,
                        presortdate, imbno, encodedimbno

    Args:
        records:          Raw feature list from get_sales_data().
        skip_org_buyers:  If True (default), skip records where Buyer1 is an
                          organization, LLC, trust, etc. Buyer2 org names are
                          preserved — they're usually co-signers on a person's sale.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
    writer.writeheader()
    skipped = 0

    for record in records:
        attrs = record.get("attributes", {})

        def get(api_field: str) -> str:
            val = attrs.get(api_field)
            return "" if val is None else str(val).strip()

        raw_buyer1 = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer1Name").upper()

        # Skip records where the primary buyer is a business/entity
        if skip_org_buyers and _is_organization_name(raw_buyer1):
            skipped += 1
            continue

        raw_address = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.PropAddress").upper()
        raw_city    = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.City").upper()
        raw_zip     = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.ZipCode")
        raw_buyer2  = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer2Name").upper()

        state = "IN"  # all Allen County records are Indiana

        city_state_zip = _build_city_state_zip(raw_city, state, raw_zip)
        recipient = format_recipient(raw_buyer1, raw_buyer2).upper()

        writer.writerow({
            "no":                 "",
            "name":               recipient,
            "contactid":          "",
            "company":            "",
            "urbanization":       "",
            "sec-primary street": "",
            "primary street":     raw_address,
            "city-state-zip":     city_state_zip,
            "ase":                "",
            "oel":                "",
            "presorttrayid":      "",
            "presortdate":        "",
            "imbno":              "",
            "encodedimbno":       "",
            "primary city":       raw_city,
            "primary state":      state,
            "primary zip":        raw_zip,
        })

    if skipped:
        print(f"  Skipped {skipped} org/entity buyer record(s)")

    return output.getvalue().encode("utf-8")


def save_to_csv(records: List[Dict[str, Any]], filename: str) -> None:
    """Write CSV bytes to `filename`."""
    if not records:
        print("No records to save!")
        return
    data = records_to_csv_bytes(records)
    with open(filename, "wb") as f:
        f.write(data)
    print(f"Data saved to: {filename}")


def generate_csv_for_period(month: int, year: int) -> Tuple[str, bytes]:
    """Fetch records for month/year and return (filename, csv_bytes).

    This is the primary helper used by the Flask app.
    """
    records = get_sales_data(month, year)
    month_name = datetime(year, month, 1).strftime("%B")
    filename = f"allen_county_sales_{month_name}_{year}.csv"
    csv_bytes = records_to_csv_bytes(records)
    return filename, csv_bytes


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    """Simple CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(description="Allen County property sales CSV exporter")
    parser.add_argument("month", type=int, nargs="?", help="Month (1-12)")
    parser.add_argument("year",  type=int, nargs="?", help="Year (e.g. 2026)")
    parser.add_argument("-o", "--output", help="Output CSV filename")
    args = parser.parse_args()

    if args.month and args.year:
        month = args.month
        year  = args.year
    else:
        while True:
            try:
                month = int(input("Enter month (1-12): "))
                if 1 <= month <= 12:
                    break
                print("Please enter a number between 1 and 12")
            except ValueError:
                print("Please enter a valid number")
        while True:
            try:
                year = int(input("Enter year (e.g., 2026): "))
                if 2000 <= year <= 2100:
                    break
                print("Please enter a valid year")
            except ValueError:
                print("Please enter a valid number")

    filename, csv_bytes = generate_csv_for_period(month, year)
    out = args.output or filename
    with open(out, "wb") as f:
        f.write(csv_bytes)
    print(f"Wrote {len(csv_bytes)} bytes to {out}")


if __name__ == "__main__":
    main()