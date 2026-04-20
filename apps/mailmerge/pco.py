"""Planning Center Online API helpers for mailmerge.

Zero dependency on Django — can be used from both Django views and the
standalone CLI scripts (pco-lists.py, pco-pull.py).
"""

from __future__ import annotations

import csv
import io
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.planningcenteronline.com/people/v2"


def _credentials() -> tuple[str, str]:
    client_id = os.environ.get("PLANNING_CENTER_CLIENT_ID", "")
    secret = os.environ.get("PLANNING_CENTER_SECRET", "")
    if not client_id or not secret:
        raise ValueError(
            "Missing PLANNING_CENTER_CLIENT_ID or PLANNING_CENTER_SECRET in environment."
        )
    return client_id, secret


def get_mailing_lists(target_category: str = "Mailing") -> list[dict]:
    """Return [{id, name}, ...] for all PCO lists in the given category."""
    client_id, secret = _credentials()
    url = f"{BASE_URL}/lists?include=category"
    mailing_lists: list[dict] = []

    while url:
        response = requests.get(url, auth=(client_id, secret), timeout=30)
        response.raise_for_status()
        data = response.json()

        categories: dict[str, str] = {}
        for item in data.get("included", []):
            if item.get("type") == "ListCategory":
                categories[item["id"]] = item["attributes"]["name"]

        for pco_list in data.get("data", []):
            category_data = (
                pco_list.get("relationships", {}).get("category", {}).get("data")
            )
            if category_data:
                category_name = categories.get(category_data.get("id"), "")
                if category_name.lower() == target_category.lower():
                    mailing_lists.append(
                        {
                            "id": pco_list["id"],
                            "name": pco_list["attributes"]["name"],
                        }
                    )

        url = data.get("links", {}).get("next")

    return mailing_lists


def get_list_people(list_id: str) -> list[dict]:
    """Return [{id, name, address}, ...] for all people in a PCO list."""
    client_id, secret = _credentials()
    url = f"{BASE_URL}/lists/{list_id}/people?include=addresses"
    people_data: list[dict] = []

    while url:
        response = requests.get(url, auth=(client_id, secret), timeout=30)
        response.raise_for_status()
        data = response.json()

        addresses: dict[str, dict] = {}
        for item in data.get("included", []):
            if item.get("type") == "Address":
                addresses[item["id"]] = item["attributes"]

        for person in data.get("data", []):
            primary_address = None
            for addr_ref in (
                person.get("relationships", {})
                .get("addresses", {})
                .get("data", [])
            ):
                addr_data = addresses.get(addr_ref["id"])
                if addr_data and addr_data.get("primary"):
                    primary_address = addr_data
                    break

            people_data.append(
                {
                    "id": person["id"],
                    "name": person["attributes"]["name"],
                    "address": primary_address,
                }
            )

        url = data.get("links", {}).get("next")

    return people_data


def list_to_csv_bytes(list_id: str, clean: bool = False) -> tuple[str, bytes]:
    """Fetch a PCO mailing list and return (filename, csv_bytes).

    Args:
        list_id: PCO list ID.
        clean:   If True, apply address standardisation (USPS abbreviations,
                 zip normalisation, etc.) via address_cleanup.clean_row().
    """
    from apps.mailmerge._csv_headers import CSV_HEADERS
    if clean:
        from apps.mailmerge.address_cleanup import clean_row, dedup_rows

    people = get_list_people(list_id)
    filename = f"mailing_list_{list_id}.csv"
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
    writer.writeheader()

    skipped = 0
    rows = []
    for person in people:
        addr = person["address"]
        city = (addr.get("city") or "").strip() if addr else ""
        state = (addr.get("state") or "").strip() if addr else ""
        zip_code = (addr.get("zip") or "").strip() if addr else ""
        street = (addr.get("street_line_1") or "").strip() if addr else ""

        # Skip records missing any required address field
        if not street or not city or not state or not zip_code:
            skipped += 1
            continue

        row = {header: "" for header in CSV_HEADERS}
        row["name"] = person["name"]
        row["contactid"] = person["id"]
        row["primary street"] = street
        row["sec-primary street"] = (addr.get("street_line_2") or "").strip()
        row["primary city"] = city
        row["primary state"] = state
        row["primary zip"] = zip_code
        row["city-state-zip"] = f"{city} {state} {zip_code}"
        rows.append(row)

    if clean:
        for row in rows:
            clean_row(row)
        rows = dedup_rows(rows)

    # Assign sequential row numbers after any deduplication
    for index, row in enumerate(rows, start=1):
        row["no"] = index
        writer.writerow(row)

    if skipped:
        print(f"  Skipped {skipped} record(s) with incomplete address")

    return filename, output.getvalue().encode("utf-8")
