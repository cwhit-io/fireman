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


class TestPreflight:
    """Tests for apps/jobs/preflight.py — the preflight rule engine."""

    def _make_pdf_bytes(self, width: float = 612, height: float = 792) -> bytes:
        """Return a minimal single-page PDF at the given dimensions (pts)."""
        import io

        from pypdf import PageObject, PdfWriter

        buf = io.BytesIO()
        w = PdfWriter()
        w.add_page(PageObject.create_blank_page(width=width, height=height))
        w.write(buf)
        return buf.getvalue()

    def test_no_trim_dims_skips_checks(self):
        from apps.jobs.preflight import run_preflight

        result = run_preflight(self._make_pdf_bytes(), 0.0, 0.0)
        # No trim dims — checks skipped, notes explain why
        assert any("skipped" in n.lower() for n in result.notes)

    def test_exact_trim_no_bleed_triggers_r1(self):
        """PDF exactly matches trim → R1 (no bleed)."""
        from apps.jobs.preflight import run_preflight

        # 3.5 × 2 in business card = 252 × 144 pt
        trim_w, trim_h = 252.0, 144.0
        result = run_preflight(self._make_pdf_bytes(trim_w, trim_h), trim_w, trim_h)
        assert "R1" in result.rules_triggered
        assert result.status == "warn"

    def test_clean_bleed_triggers_r2(self):
        """PDF with ~9pt bleed per side → R2 (clean bleed)."""
        from apps.jobs.preflight import run_preflight

        trim_w, trim_h = 252.0, 144.0
        bleed = 9.0
        result = run_preflight(
            self._make_pdf_bytes(trim_w + bleed * 2, trim_h + bleed * 2),
            trim_w,
            trim_h,
        )
        assert "R2" in result.rules_triggered
        assert result.status == "ok"

    def test_canva_style_triggers_r3(self):
        """PDF with ~17pt overage per side → R3 (Canva crop marks)."""
        from apps.jobs.preflight import run_preflight

        trim_w, trim_h = 252.0, 144.0
        canva_margin = 17.0
        result = run_preflight(
            self._make_pdf_bytes(trim_w + canva_margin * 2, trim_h + canva_margin * 2),
            trim_w,
            trim_h,
        )
        assert "R3" in result.rules_triggered

    def test_oversized_unrecognized_triggers_r4(self):
        """PDF with >22pt overage per side → R4 (oversized, unrecognized)."""
        from apps.jobs.preflight import run_preflight

        trim_w, trim_h = 252.0, 144.0
        big_margin = 30.0
        result = run_preflight(
            self._make_pdf_bytes(trim_w + big_margin * 2, trim_h + big_margin * 2),
            trim_w,
            trim_h,
        )
        assert "R4" in result.rules_triggered
        assert result.status == "warn"

    def test_wrong_size_same_ar_triggers_r5(self):
        """PDF at half size but same AR → R5 (scale to trim)."""
        from apps.jobs.preflight import run_preflight

        trim_w, trim_h = 252.0, 144.0
        result = run_preflight(
            self._make_pdf_bytes(trim_w * 0.8, trim_h * 0.8),
            trim_w,
            trim_h,
        )
        assert "R5" in result.rules_triggered
        assert result.status == "warn"

    def test_wrong_size_ar_mismatch_triggers_r6(self):
        """PDF at completely different AR → R6 (squished)."""
        from apps.jobs.preflight import run_preflight

        trim_w, trim_h = 252.0, 144.0
        result = run_preflight(
            self._make_pdf_bytes(trim_h, trim_w),  # portrait vs landscape
            trim_w,
            trim_h,
        )
        assert "R6" in result.rules_triggered
        assert result.status == "warn"

    def test_empty_bytes_handled_gracefully(self):
        from apps.jobs.preflight import run_preflight

        result = run_preflight(b"", 252.0, 144.0)
        assert result.status == "ok"  # no crash; notes explain skip

    def test_run_preflight_for_job_saves_results(self):
        """services.run_preflight_for_job() persists preflight data on the job."""
        import io

        from django.core.files.base import ContentFile
        from pypdf import PageObject, PdfWriter

        from apps.impose.models import ImpositionTemplate
        from apps.jobs.models import PrintJob
        from apps.jobs.services import run_preflight_for_job

        tmpl = ImpositionTemplate.objects.create(
            name="Preflight Test Tmpl",
            sheet_width=900,
            sheet_height=1368,
            columns=1,
            rows=1,
            cut_width=252,
            cut_height=144,
        )

        # Build PDF at exact trim size (triggers R1)
        buf = io.BytesIO()
        w = PdfWriter()
        w.add_page(PageObject.create_blank_page(width=252, height=144))
        w.write(buf)
        pdf_bytes = buf.getvalue()

        job = PrintJob.objects.create(name="pf.pdf", imposition_template=tmpl)
        job.file.save("pf.pdf", ContentFile(pdf_bytes), save=True)

        run_preflight_for_job(job, pdf_bytes=pdf_bytes)
        job.refresh_from_db()

        assert job.preflight_status in ("ok", "warn", "error")
        assert isinstance(job.preflight_rules_triggered, list)
        assert isinstance(job.preflight_messages, list)
        assert job.preflight_acknowledged is False
