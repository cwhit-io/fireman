import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.mailmerge.models import MailMergeJob
from apps.mailmerge.services import (
    _address_text_stream,
    _escape_pdf_string,
    build_address_steprepeat,
    build_artwork_gangup,
    compute_gangup_grid,
    inspect_artwork_pdf,
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


def _make_two_page_pdf() -> bytes:
    """Return a valid 2-page PDF: page 1 = 432×288 (front), page 2 = 432×288 (address)."""
    from pypdf import PageObject, PdfWriter

    writer = PdfWriter()
    writer.add_page(PageObject.create_blank_page(width=432, height=288))
    writer.add_page(PageObject.create_blank_page(width=432, height=288))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


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

    def test_custom_addr_x_y(self):
        record = {"primary street": "123 MAIN ST", "city-state-zip": "CITY ST 12345"}
        # Custom position: x=100pt, y=50pt
        stream = _address_text_stream(record, card_w=432, card_h=288, addr_x=100.0, addr_y=50.0)
        assert b"100.000" in stream
        assert b"50.000" in stream


# ── Unit tests: inspect_artwork_pdf ──────────────────────────────────────


class TestInspectArtworkPdf:
    def test_single_page(self):
        info = inspect_artwork_pdf(io.BytesIO(_make_minimal_pdf()))
        assert info["page_count"] == 1
        assert len(info["pages"]) == 1
        p = info["pages"][0]
        assert p["width_pt"] == pytest.approx(432, abs=1)
        assert p["height_pt"] == pytest.approx(288, abs=1)
        assert p["width_in"] == pytest.approx(6.0, abs=0.1)
        assert p["height_in"] == pytest.approx(4.0, abs=0.1)

    def test_two_page(self):
        info = inspect_artwork_pdf(io.BytesIO(_make_two_page_pdf()))
        assert info["page_count"] == 2
        assert len(info["pages"]) == 2

    def test_empty_returns_zero(self):
        info = inspect_artwork_pdf(io.BytesIO(b""))
        assert info["page_count"] == 0
        assert info["pages"] == []


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

    def test_two_page_artwork_produces_two_pages_per_record(self):
        from pypdf import PdfReader

        records = parse_usps_csv(io.BytesIO(_sample_csv_bytes()))
        out = io.BytesIO()
        count = merge_postcards(io.BytesIO(_make_two_page_pdf()), records, out, merge_page=2)
        assert count == 1
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 2  # 2 artwork pages × 1 record

    def test_two_page_multiple_records(self):
        from pypdf import PdfReader

        csv_bytes = (
            b"no,name,primary street,city-state-zip,imbno\n"
            b"1,ALICE,123 MAIN ST,CITY ST 12345,IMB001\n"
            b"2,BOB,456 OAK AVE,TOWN CA 90210,IMB002\n"
        )
        records = parse_usps_csv(io.BytesIO(csv_bytes))
        out = io.BytesIO()
        count = merge_postcards(io.BytesIO(_make_two_page_pdf()), records, out, merge_page=2)
        assert count == 2
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 4  # 2 artwork pages × 2 records

    def test_custom_address_position(self):
        records = parse_usps_csv(io.BytesIO(_sample_csv_bytes()))
        out = io.BytesIO()
        count = merge_postcards(
            io.BytesIO(_make_minimal_pdf()),
            records,
            out,
            addr_x_in=1.0,
            addr_y_in=1.0,
        )
        assert count == 1

    def test_merge_page_clamped_to_valid_range(self):
        """merge_page out of range should be clamped, not raise."""
        records = parse_usps_csv(io.BytesIO(_sample_csv_bytes()))
        out = io.BytesIO()
        # merge_page=99 should be clamped to 1 for a single-page artwork
        count = merge_postcards(io.BytesIO(_make_minimal_pdf()), records, out, merge_page=99)
        assert count == 1


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

    def test_post_stores_merge_page_and_address_position(self, client, monkeypatch):
        monkeypatch.setattr(
            "apps.mailmerge.views.process_mail_merge_task.delay",
            lambda *a, **kw: None,
        )
        artwork = SimpleUploadedFile(
            "card.pdf", _make_two_page_pdf(), content_type="application/pdf"
        )
        csv_f = SimpleUploadedFile(
            "addr.csv", _sample_csv_bytes(), content_type="text/csv"
        )
        response = client.post(
            reverse("mailmerge:upload"),
            {
                "artwork_file": artwork,
                "csv_file": csv_f,
                "name": "Two Page Run",
                "merge_page": "2",
                "addr_x_in": "1.5",
                "addr_y_in": "2.0",
            },
        )
        assert response.status_code == 302
        job = MailMergeJob.objects.get(name="Two Page Run")
        assert job.merge_page == 2
        assert job.artwork_page_count == 2
        assert float(job.addr_x_in) == pytest.approx(1.5)
        assert float(job.addr_y_in) == pytest.approx(2.0)


class TestMailMergeArtworkInspectView:
    def test_post_no_file_returns_400(self, client):
        response = client.post(reverse("mailmerge:inspect_artwork"), {})
        assert response.status_code == 400

    def test_post_non_pdf_returns_400(self, client):
        f = SimpleUploadedFile("art.txt", b"not pdf", content_type="text/plain")
        response = client.post(reverse("mailmerge:inspect_artwork"), {"artwork_file": f})
        assert response.status_code == 400

    def test_post_valid_pdf_returns_page_info(self, client):
        f = SimpleUploadedFile(
            "card.pdf", _make_minimal_pdf(), content_type="application/pdf"
        )
        response = client.post(reverse("mailmerge:inspect_artwork"), {"artwork_file": f})
        assert response.status_code == 200
        import json
        data = json.loads(response.content)
        assert data["page_count"] == 1
        assert len(data["pages"]) == 1

    def test_post_two_page_pdf_returns_two_pages(self, client):
        f = SimpleUploadedFile(
            "card.pdf", _make_two_page_pdf(), content_type="application/pdf"
        )
        response = client.post(reverse("mailmerge:inspect_artwork"), {"artwork_file": f})
        assert response.status_code == 200
        import json
        data = json.loads(response.content)
        assert data["page_count"] == 2


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


# ── Unit tests: compute_gangup_grid ──────────────────────────────────────


class TestComputeGangupGrid:
    def test_postcard_6x4_on_12x18(self):
        # 6×4" card (432×288 pt) on 12×18" sheet (864×1296 pt)
        cols, rows = compute_gangup_grid(432, 288, 864, 1296)
        assert cols >= 2
        assert rows >= 2
        assert cols * rows >= 6

    def test_returns_at_least_one_cell(self):
        # Even a very large card should return 1×1
        cols, rows = compute_gangup_grid(900, 900, 864, 1296)
        assert cols >= 1
        assert rows >= 1

    def test_rotation_used_when_better(self):
        # 4×6 portrait card: 4"×6" (288×432 pt)
        # Normal: 864/288=3 cols, 1296/432=3 rows = 9
        # Rotated (card 432×288): 864/432=2 cols, 1296/288=4 rows = 8
        # So normal wins here
        cols, rows = compute_gangup_grid(288, 432, 864, 1296)
        assert cols * rows >= 6


# ── Unit tests: build_artwork_gangup ────────────────────────────────────


class TestBuildArtworkGangup:
    def test_single_page_produces_one_sheet(self):
        from pypdf import PdfReader

        out = io.BytesIO()
        build_artwork_gangup(
            io.BytesIO(_make_minimal_pdf()),
            cols=2, rows=2,
            sheet_w_pt=864, sheet_h_pt=1296,
            output_pdf=out,
        )
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 1  # one press sheet for single-page artwork

    def test_two_page_produces_two_sheets(self):
        from pypdf import PdfReader

        out = io.BytesIO()
        build_artwork_gangup(
            io.BytesIO(_make_two_page_pdf()),
            cols=2, rows=2,
            sheet_w_pt=864, sheet_h_pt=1296,
            output_pdf=out,
        )
        out.seek(0)
        reader = PdfReader(out)
        assert len(reader.pages) == 2  # one sheet per artwork page


# ── Unit tests: build_address_steprepeat ────────────────────────────────


class TestBuildAddressSteprepeat:
    def test_basic(self):
        from pypdf import PdfReader

        records = parse_usps_csv(io.BytesIO(_sample_csv_bytes()))
        out = io.BytesIO()
        count = build_address_steprepeat(
            records,
            card_w=432, card_h=288,
            cols=2, rows=2,
            sheet_w=864, sheet_h=1296,
            addr_x=108, addr_y=180,
            output_pdf=out,
        )
        assert count == 1
        out.seek(0)
        assert out.read(4) == b"%PDF"

    def test_multiple_records_produce_multiple_sheets(self):
        from pypdf import PdfReader

        csv_bytes = (
            b"no,name,primary street,city-state-zip,imbno\n"
            b"1,ALICE,123 MAIN ST,CITY ST 12345,IMB001\n"
            b"2,BOB,456 OAK AVE,TOWN CA 90210,IMB002\n"
            b"3,CAROL,789 ELM RD,METRO TX 75001,IMB003\n"
            b"4,DAVE,321 PINE ST,SUBURB FL 33101,IMB004\n"
            b"5,EVE,654 CEDAR AV,LAKE WI 53201,IMB005\n"
        )
        records = parse_usps_csv(io.BytesIO(csv_bytes))
        out = io.BytesIO()
        count = build_address_steprepeat(
            records,
            card_w=432, card_h=288,
            cols=2, rows=2,
            sheet_w=864, sheet_h=1296,
            addr_x=None, addr_y=None,
            output_pdf=out,
        )
        assert count == 5
        out.seek(0)
        reader = PdfReader(out)
        # 5 records, 4 per sheet → 2 sheets
        assert len(reader.pages) == 2


# ── Integration tests: new views ─────────────────────────────────────────


class TestMailMergeEditView:
    def test_get_returns_200(self, client):
        job = MailMergeJob.objects.create(
            name="Edit Me",
            artwork_page_count=1,
            merge_page=1,
        )
        response = client.get(reverse("mailmerge:edit", kwargs={"pk": job.pk}))
        assert response.status_code == 200

    def test_post_updates_position_and_redirects(self, client, monkeypatch):
        monkeypatch.setattr(
            "apps.mailmerge.views.process_mail_merge_task.delay",
            lambda *a, **kw: None,
        )
        job = MailMergeJob.objects.create(
            name="Edit Me",
            artwork_page_count=1,
            merge_page=1,
            addr_x_in=None,
            addr_y_in=None,
        )
        response = client.post(
            reverse("mailmerge:edit", kwargs={"pk": job.pk}),
            {"name": "Edit Me Updated", "merge_page": "1",
             "addr_x_in": "1.5", "addr_y_in": "2.0"},
        )
        assert response.status_code == 302
        job.refresh_from_db()
        assert float(job.addr_x_in) == pytest.approx(1.5)
        assert float(job.addr_y_in) == pytest.approx(2.0)
        assert job.status == MailMergeJob.Status.PENDING


class TestMailMergeArtworkServeView:
    def test_get_returns_artwork_pdf(self, client):
        artwork = SimpleUploadedFile(
            "card.pdf", _make_minimal_pdf(), content_type="application/pdf"
        )
        job = MailMergeJob.objects.create(name="Serve Test", artwork_file=artwork)
        response = client.get(reverse("mailmerge:serve_artwork", kwargs={"pk": job.pk}))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_get_no_artwork_returns_404(self, client):
        job = MailMergeJob.objects.create(name="No Art")
        response = client.get(reverse("mailmerge:serve_artwork", kwargs={"pk": job.pk}))
        assert response.status_code == 404


class TestMailMergeDownloadGangupView:
    def test_download_gangup_file(self, client, tmp_path):
        from django.core.files.base import ContentFile

        job = MailMergeJob.objects.create(name="Gangup Test")
        job.gangup_file.save("gangup.pdf", ContentFile(_make_minimal_pdf()), save=True)
        response = client.get(reverse("mailmerge:download_gangup", kwargs={"pk": job.pk}))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_download_gangup_missing_returns_404(self, client):
        job = MailMergeJob.objects.create(name="No Gangup")
        response = client.get(reverse("mailmerge:download_gangup", kwargs={"pk": job.pk}))
        assert response.status_code == 404


class TestMailMergeDownloadAddressPdfView:
    def test_download_address_pdf(self, client):
        from django.core.files.base import ContentFile

        job = MailMergeJob.objects.create(name="Addr Test")
        job.address_pdf_file.save("addresses.pdf", ContentFile(_make_minimal_pdf()), save=True)
        response = client.get(reverse("mailmerge:download_addresses", kwargs={"pk": job.pk}))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_download_address_pdf_missing_returns_404(self, client):
        job = MailMergeJob.objects.create(name="No Addr")
        response = client.get(reverse("mailmerge:download_addresses", kwargs={"pk": job.pk}))
        assert response.status_code == 404
