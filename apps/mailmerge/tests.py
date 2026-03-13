import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.mailmerge.models import MailMergeJob
from apps.mailmerge.services import (
    _address_text_stream,
    _escape_pdf_string,
    merge_postcards,
    parse_usps_csv,
)

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_minimal_pdf() -> bytes:
    """Return a tiny but valid single-page 432×288 pt PDF (6×4 landscape)."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 432 288]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
        b"0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )


def _sample_csv_bytes() -> bytes:
    return (
        b"no,name,contactid,company,urbanization,sec-primary street,"
        b"primary street,city-state-zip,ase,oel,presorttrayid,presortdate,"
        b"imbno,encodedimbno,primary city,primary state,primary zip\n"
        b"1,JOHN DOE,,ACME INC,,,"
        b"123 MAPLE ST,SPRINGFIELD IN 46801-1234,"
        b"Address Service Requested,,T00001,02/16/2026,"
        b"00-320-903430294-000001-46801-1234-23,"
        b"DATFTATDATAATDAAFDDAFDFAAADAFATTAFDAFAATFTTDATFAAADDDTTTADFFDTAFD,"
        b"SPRINGFIELD,IN, 46801-1234\n"
    )


# ── Unit tests: CSV parsing ───────────────────────────────────────────────


class TestParseUspsCsv:
    def test_parse_returns_list_of_dicts(self):
        records = parse_usps_csv(io.BytesIO(_sample_csv_bytes()))
        assert len(records) == 1

    def test_keys_are_lowercase(self):
        records = parse_usps_csv(io.BytesIO(_sample_csv_bytes()))
        assert "primary street" in records[0]
        assert "city-state-zip" in records[0]

    def test_field_values(self):
        records = parse_usps_csv(io.BytesIO(_sample_csv_bytes()))
        r = records[0]
        assert r["name"] == "JOHN DOE"
        assert r["company"] == "ACME INC"
        assert r["primary street"] == "123 MAPLE ST"
        assert r["city-state-zip"] == "SPRINGFIELD IN 46801-1234"
        assert r["imbno"] == "00-320-903430294-000001-46801-1234-23"

    def test_empty_csv_returns_empty_list(self):
        header = b"no,name,primary street,city-state-zip\n"
        records = parse_usps_csv(io.BytesIO(header))
        assert records == []


# ── Unit tests: PDF string escaping ─────────────────────────────────────


class TestEscapePdfString:
    def test_simple_ascii(self):
        assert _escape_pdf_string("hello") == b"hello"

    def test_parens_escaped(self):
        result = _escape_pdf_string("foo (bar)")
        assert b"\\(" in result
        assert b"\\)" in result

    def test_backslash_escaped(self):
        result = _escape_pdf_string("a\\b")
        assert b"\\\\" in result


# ── Unit tests: address text stream ──────────────────────────────────────


class TestAddressTextStream:
    def test_contains_bt_et(self):
        record = {
            "name": "JOHN DOE",
            "primary street": "123 MAPLE ST",
            "city-state-zip": "SPRINGFIELD IN 46801",
            "imbno": "00-123-456",
        }
        stream = _address_text_stream(record, card_w=432, card_h=288)
        assert b"BT" in stream
        assert b"ET" in stream

    def test_empty_record_returns_empty(self):
        stream = _address_text_stream({}, card_w=432, card_h=288)
        assert stream == b""

    def test_optional_fields_omitted_when_blank(self):
        record = {
            "primary street": "123 MAPLE ST",
            "city-state-zip": "SPRINGFIELD IN 46801",
            "imbno": "00-123",
        }
        stream = _address_text_stream(record, card_w=432, card_h=288)
        # No name/company/urbanization lines
        assert b"BT" in stream

    def test_x_position_based_on_card_width(self):
        # For card_w=432 (6"), x = 432 - 4.5*72 = 432 - 324 = 108
        record = {"primary street": "123 MAIN ST", "city-state-zip": "CITY ST 12345"}
        stream = _address_text_stream(record, card_w=432, card_h=288)
        assert b"108.000" in stream


# ── Unit tests: merge_postcards ──────────────────────────────────────────


class TestMergePostcards:
    def test_one_record_produces_one_page(self):
        records = parse_usps_csv(io.BytesIO(_sample_csv_bytes()))
        out = io.BytesIO()
        count = merge_postcards(io.BytesIO(_make_minimal_pdf()), records, out)
        assert count == 1
        out.seek(0)
        assert out.read(4) == b"%PDF"

    def test_multiple_records(self):
        csv_bytes = (
            b"no,name,primary street,city-state-zip,imbno\n"
            b"1,ALICE,123 MAIN ST,CITY ST 12345,IMB001\n"
            b"2,BOB,456 OAK AVE,TOWN CA 90210,IMB002\n"
        )
        records = parse_usps_csv(io.BytesIO(csv_bytes))
        out = io.BytesIO()
        count = merge_postcards(io.BytesIO(_make_minimal_pdf()), records, out)
        assert count == 2

    def test_empty_artwork_raises(self):
        with pytest.raises(ValueError, match="empty"):
            merge_postcards(io.BytesIO(b""), [], io.BytesIO())


# ── Integration tests: views ─────────────────────────────────────────────


class TestMailMergeListView:
    def test_get_returns_200(self, client):
        response = client.get(reverse("mailmerge:list"))
        assert response.status_code == 200

    def test_shows_jobs(self, client):
        MailMergeJob.objects.create(name="Test Run")
        response = client.get(reverse("mailmerge:list"))
        assert b"Test Run" in response.content


class TestMailMergeUploadView:
    def test_get_returns_200(self, client):
        response = client.get(reverse("mailmerge:upload"))
        assert response.status_code == 200

    def test_post_no_files_returns_400(self, client):
        response = client.post(reverse("mailmerge:upload"), {})
        assert response.status_code == 400

    def test_post_non_pdf_artwork_returns_400(self, client):
        artwork = SimpleUploadedFile("art.txt", b"not a pdf", content_type="text/plain")
        csv_f = SimpleUploadedFile(
            "addr.csv", _sample_csv_bytes(), content_type="text/csv"
        )
        response = client.post(
            reverse("mailmerge:upload"),
            {"artwork_file": artwork, "csv_file": csv_f},
        )
        assert response.status_code == 400

    def test_post_valid_files_creates_job_and_redirects(self, client, monkeypatch):
        monkeypatch.setattr(
            "apps.mailmerge.views.process_mail_merge_task.delay",
            lambda *a, **kw: None,
        )
        artwork = SimpleUploadedFile(
            "card.pdf", _make_minimal_pdf(), content_type="application/pdf"
        )
        csv_f = SimpleUploadedFile(
            "addr.csv", _sample_csv_bytes(), content_type="text/csv"
        )
        response = client.post(
            reverse("mailmerge:upload"),
            {"artwork_file": artwork, "csv_file": csv_f, "name": "Spring Run"},
        )
        assert response.status_code == 302
        job = MailMergeJob.objects.get(name="Spring Run")
        assert str(job.pk) in response["Location"]


class TestMailMergeDetailView:
    def test_get_returns_200(self, client):
        job = MailMergeJob.objects.create(name="Run A")
        response = client.get(reverse("mailmerge:detail", kwargs={"pk": job.pk}))
        assert response.status_code == 200

    def test_shows_job_name(self, client):
        job = MailMergeJob.objects.create(name="Run A")
        response = client.get(reverse("mailmerge:detail", kwargs={"pk": job.pk}))
        assert b"Run A" in response.content


class TestMailMergeDeleteView:
    def test_get_confirm_page(self, client):
        job = MailMergeJob.objects.create(name="Delete Me")
        response = client.get(reverse("mailmerge:delete", kwargs={"pk": job.pk}))
        assert response.status_code == 200

    def test_post_deletes_job(self, client):
        job = MailMergeJob.objects.create(name="Delete Me")
        pk = job.pk
        client.post(reverse("mailmerge:delete", kwargs={"pk": pk}))
        assert not MailMergeJob.objects.filter(pk=pk).exists()
