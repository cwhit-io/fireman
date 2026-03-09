import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _make_minimal_pdf() -> bytes:
    """Return a tiny but valid single-page PDF."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
        b"0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )


class TestPrintJobModel:
    def test_create_job(self):
        from apps.jobs.models import PrintJob

        job = PrintJob.objects.create(name="test.pdf")
        assert job.pk is not None
        assert job.status == PrintJob.Status.PENDING

    def test_page_size_label_without_dimensions(self):
        from apps.jobs.models import PrintJob

        job = PrintJob(name="x.pdf")
        assert job.page_size_label == "—"

    def test_page_size_label_with_dimensions(self):
        from apps.jobs.models import PrintJob

        job = PrintJob(name="x.pdf", page_width=612, page_height=792)
        assert "8.5" in job.page_size_label
        assert "11" in job.page_size_label


class TestJobUploadView:
    def test_get_upload_page(self, client):
        response = client.get(reverse("jobs:upload"))
        assert response.status_code == 200

    def test_upload_no_file(self, client):
        response = client.post(reverse("jobs:upload"), {})
        assert response.status_code == 400

    def test_upload_non_pdf(self, client):
        f = SimpleUploadedFile("test.txt", b"hello", content_type="text/plain")
        response = client.post(reverse("jobs:upload"), {"file": f})
        assert response.status_code == 400

    def test_upload_pdf(self, client, monkeypatch):
        monkeypatch.setattr(
            "apps.jobs.views.process_job_task.delay", lambda *a, **kw: None
        )
        from apps.impose.models import ImpositionTemplate

        tmpl = ImpositionTemplate.objects.create(
            name="Test Template",
            sheet_width=900,
            sheet_height=1368,
            columns=1,
            rows=1,
        )
        pdf = SimpleUploadedFile(
            "sample.pdf", _make_minimal_pdf(), content_type="application/pdf"
        )
        response = client.post(
            reverse("jobs:upload"), {"file": pdf, "template_id": str(tmpl.pk)}
        )
        # redirects to detail page
        assert response.status_code == 302

    def test_upload_pdf_with_options(self, client, monkeypatch):
        """Uploading a PDF with duplex/unique flags saves them on the job."""
        monkeypatch.setattr(
            "apps.jobs.views.process_job_task.delay", lambda *a, **kw: None
        )
        from apps.impose.models import ImpositionTemplate
        from apps.jobs.models import PrintJob

        tmpl = ImpositionTemplate.objects.create(
            name="Test Template 2",
            sheet_width=900,
            sheet_height=1368,
            columns=1,
            rows=1,
        )
        pdf = SimpleUploadedFile(
            "flyer.pdf", _make_minimal_pdf(), content_type="application/pdf"
        )
        response = client.post(
            reverse("jobs:upload"),
            {
                "file": pdf,
                "template_id": str(tmpl.pk),
                "is_double_sided": "on",
                "pages_are_unique": "on",
            },
        )
        assert response.status_code == 302
        job = PrintJob.objects.latest("created_at")
        assert job.is_double_sided is True
        assert job.pages_are_unique is True

    def test_upload_corrupt_pdf_rejected(self, client):
        """Completely unreadable bytes are rejected with an error message."""
        f = SimpleUploadedFile(
            "bad.pdf", b"NOT_A_PDF_AT_ALL", content_type="application/pdf"
        )
        response = client.post(reverse("jobs:upload"), {"file": f})
        assert response.status_code == 400


class TestValidateAndRepairPDF:
    def test_clean_pdf_passes(self):
        import io

        from django.core.files.base import ContentFile
        from pypdf import PageObject, PdfWriter

        from apps.jobs.models import PrintJob
        from apps.jobs.services import validate_and_repair_pdf

        buf = io.BytesIO()
        w = PdfWriter()
        w.add_page(PageObject.create_blank_page(width=612, height=792))
        w.write(buf)
        pdf_bytes = buf.getvalue()

        job = PrintJob.objects.create(name="ok.pdf")
        job.file.save("ok.pdf", ContentFile(pdf_bytes), save=True)
        repaired, warnings = validate_and_repair_pdf(job.file)
        assert repaired is not None
        assert warnings == []

    def test_unreadable_bytes_returns_none(self):
        from django.core.files.base import ContentFile

        from apps.jobs.models import PrintJob
        from apps.jobs.services import validate_and_repair_pdf

        job = PrintJob.objects.create(name="corrupt.pdf")
        job.file.save("corrupt.pdf", ContentFile(b"GARBAGE_BYTES_NOT_PDF"), save=True)
        repaired, warnings = validate_and_repair_pdf(job.file)
        assert repaired is None
        assert len(warnings) > 0


class TestExtractPDFMetadata:
    def test_extract_metadata(self, tmp_path):
        from django.core.files.base import ContentFile

        from apps.jobs.models import PrintJob
        from apps.jobs.services import extract_pdf_metadata

        pdf_bytes = _make_minimal_pdf()
        job = PrintJob.objects.create(name="meta.pdf")
        job.file.save("meta.pdf", ContentFile(pdf_bytes), save=True)

        extract_pdf_metadata(job)
        job.refresh_from_db()
        assert job.page_count == 1
        assert float(job.page_width) == pytest.approx(612.0)
        assert float(job.page_height) == pytest.approx(792.0)
