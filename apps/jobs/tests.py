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
        monkeypatch.setattr("apps.jobs.views.process_job_task.delay", lambda *a, **kw: None)
        pdf = SimpleUploadedFile("sample.pdf", _make_minimal_pdf(), content_type="application/pdf")
        response = client.post(reverse("jobs:upload"), {"file": pdf})
        # redirects to detail page
        assert response.status_code == 302

    def test_job_list(self, client):
        response = client.get(reverse("jobs:list"))
        assert response.status_code == 200


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
