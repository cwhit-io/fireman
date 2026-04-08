"""Allen County sales extractor — core functionality.

This module provides:
- get_sales_data(month, year) -> list of records
- records_to_csv_bytes(records) -> bytes (CSV)
- save_to_csv(records, filename)
- generate_csv_for_period(month, year) -> (filename, bytes)

The module can be used from the CLI or imported by the Flask app.
"""

from __future__ import annotations

import csv
import io
import requests
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

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

# Output column order — matches your mail presort layout exactly
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

FIELD_MAP = {
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.PropAddress": "Property Address",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.City": "City",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.ZipCode": "ZIP Code",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.SaleDate": "Sale Date",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer1Name": "Buyer 1",
    "GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer2Name": "Buyer 2",
}


def get_sales_data(month: int, year: int, batch_size: int = 1000) -> List[Dict[str, Any]]:
    """Fetch sales records from the GIS API for the given month/year.

    Returns the raw feature list (may be empty).
    """
    start_date = f"{month}/1/{year}"
    if month == 12:
        end_month = 1
        end_year = year + 1
    else:
        end_month = month + 1
        end_year = year
    end_date = f"{end_month}/1/{end_year}"

    where_clause = (
        "GISPublished.SDE.Parcel_Point.OBJECTID > 0 "
        "and GISPublished.sde.AssessorSalesBuildingsParcelInfo.Valid = 1 "
        "and (GISPublished.sde.AssessorSalesBuildingsParcelInfo.ClassGroupDescription = 'Res Unimproved' "
        "or GISPublished.sde.AssessorSalesBuildingsParcelInfo.ClassGroupDescription = 'Res Improved') "
        f"and GISPublished.sde.AssessorSalesBuildingsParcelInfo.SaleDate > date '{start_date}' "
        f"AND GISPublished.sde.AssessorSalesBuildingsParcelInfo.SaleDate < date '{end_date}'"
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


def convert_timestamp(timestamp_ms: Optional[int]) -> str:
    """Convert epoch milliseconds to YYYY-MM-DD (returns empty string for falsy input)."""
    if not timestamp_ms:
        return ""
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d")


def _is_organization_name(name: str) -> bool:
    if not name:
        return False
    n = name.upper()
    org_indicators = [
        'LLC', 'INC', 'CORP', 'CO', 'COMPANY', 'TRUST', 'BANK', 'ASSOCIATES', 'HOLDINGS',
        'LP', 'L.P.', 'LLP', 'C/O'
    ]
    if any(tok in n for tok in org_indicators):
        return True
    if 'AKA' in n or 'A.K.A' in n or 'ALSO KNOWN' in n:
        return True
    return False


def _split_person_name(name: str) -> tuple[str, str]:
    """Return (given-part, last-name) for a likely person name.

    Handles "Last, First" and removes common suffixes (Jr, Sr, II, III).
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

    - If both look like people and share a last name -> "Given1 & Given2 Last"
    - Otherwise join full names with ` & `.
    - Empty values are ignored.
    - Treat names containing LLC/INC/aka as organizations/complex and avoid parsing.
    """
    b1 = (buyer1 or '').strip()
    b2 = (buyer2 or '').strip()

    if not b1 and not b2:
        return ''
    if not b1:
        return b2
    if not b2:
        return b1

    if _is_organization_name(b1) or _is_organization_name(b2):
        return f"{b1} & {b2}"

    g1, l1 = _split_person_name(b1)
    g2, l2 = _split_person_name(b2)

    if l1 and l2 and l1.lower() == l2.lower():
        return f"{g1} & {g2} {l1}"

    return f"{b1} & {b2}"


def _build_city_state_zip(city: str, state: str, zip_code: str) -> str:
    """Format the combined city-state-zip field, e.g. 'SPRINGFIELD IN 46801-1234'."""
    parts = [p for p in [city, state, zip_code] if p]
    return " ".join(parts)


def records_to_csv_bytes(records: List[Dict[str, Any]]) -> bytes:
    """Serialize API records to the mail presort CSV format and return UTF-8 bytes.

    Populated columns:  name, primary street, city-state-zip,
                        primary city, primary state, primary zip
    Blank columns:      no, contactid, company, urbanization,
                        sec-primary street, ase, oel, presorttrayid,
                        presortdate, imbno, encodedimbno
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
    writer.writeheader()

    for record in records:
        attrs = record.get("attributes", {})

        # --- pull raw values ---
        def get(api_field: str) -> str:
            val = attrs.get(api_field)
            return "" if val is None else str(val).strip()

        raw_address = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.PropAddress").upper()
        raw_city    = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.City").upper()
        raw_zip     = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.ZipCode")
        raw_buyer1  = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer1Name").upper()
        raw_buyer2  = get("GISPublished.sde.AssessorSalesBuildingsParcelInfo.Buyer2Name").upper()

        state = "IN"  # all Allen County records are Indiana

        city_state_zip = _build_city_state_zip(raw_city, state, raw_zip)
        recipient = format_recipient(raw_buyer1, raw_buyer2).upper()

        writer.writerow({
            "no":                  "",
            "name":                recipient,
            "contactid":           "",
            "company":             "",
            "urbanization":        "",
            "sec-primary street":  "",
            "primary street":      raw_address,
            "city-state-zip":      city_state_zip,
            "ase":                 "",
            "oel":                 "",
            "presorttrayid":       "",
            "presortdate":         "",
            "imbno":               "",
            "encodedimbno":        "",
            "primary city":        raw_city,
            "primary state":       state,
            "primary zip":         raw_zip,
        })

    return output.getvalue().encode("utf-8")


def save_to_csv(records: List[Dict[str, Any]], filename: str) -> None:
    """Write CSV bytes to `filename`."""
    if not records:
        print("No records to save!")
        return
    data = records_to_csv_bytes(records)
    with open(filename, "wb") as f:
        f.write(data)
    print(f"\nData saved to: {filename}")


def generate_csv_for_period(month: int, year: int) -> Tuple[str, bytes]:
    """Fetch records for month/year and return (filename, csv_bytes).

    This is the helper used by the Flask app.
    """
    records = get_sales_data(month, year)
    month_name = datetime(year, month, 1).strftime("%B")
    filename = f"allen_county_sales_{month_name}_{year}.csv"
    csv_bytes = records_to_csv_bytes(records)
    return filename, csv_bytes


def main() -> None:
    """Simple CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(description="Allen County property sales CSV exporter")
    parser.add_argument("month", type=int, nargs="?", help="Month (1-12)")
    parser.add_argument("year", type=int, nargs="?", help="Year (e.g. 2026)")
    parser.add_argument("-o", "--output", help="Output CSV filename")
    args = parser.parse_args()

    if args.month and args.year:
        month = args.month
        year = args.year
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