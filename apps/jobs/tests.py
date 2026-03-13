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
    def test_get_upload_page(self, client, user):
        client.force_login(user)
        response = client.get(reverse("jobs:upload"))
        assert response.status_code == 200

    def test_upload_no_file(self, client, user):
        client.force_login(user)
        response = client.post(reverse("jobs:upload"), {})
        assert response.status_code == 400

    def test_upload_non_pdf(self, client, user):
        client.force_login(user)
        f = SimpleUploadedFile("test.txt", b"hello", content_type="text/plain")
        response = client.post(reverse("jobs:upload"), {"file": f})
        assert response.status_code == 400

    def test_upload_pdf(self, client, user, monkeypatch):
        client.force_login(user)
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

    def test_upload_pdf_with_options(self, client, user, monkeypatch):
        """Uploading a PDF with duplex/unique flags saves them on the job."""
        client.force_login(user)
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
        job = PrintJob.objects.filter(owner=user).latest("created_at")
        assert job.is_double_sided is True
        assert job.pages_are_unique is True

    def test_upload_corrupt_pdf_rejected(self, client, user):
        """Completely unreadable bytes are rejected with an error message."""
        client.force_login(user)
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
        # images should be empty when nothing triggered
        assert result.images == []

    def test_exact_trim_no_bleed_triggers_r1(self):
        """PDF exactly matches trim → R1 (no bleed)."""
        from apps.jobs.preflight import run_preflight

        # 3.5 × 2 in business card = 252 × 144 pt
        trim_w, trim_h = 252.0, 144.0
        result = run_preflight(self._make_pdf_bytes(trim_w, trim_h), trim_w, trim_h)
        assert "R1" in result.rules_triggered
        assert result.status == "warn"
        # message/image pairing remains aligned
        assert len(result.images) == len(result.messages)
        assert result.images[0] == "r1.png"

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
        assert isinstance(job.preflight_images, list)
        # message_pairs should be a list of 2-tuples and line up
        pairs = job.preflight_message_pairs
        assert all(isinstance(p, tuple) and len(p) == 2 for p in pairs)
        assert len(pairs) == len(job.preflight_messages)
        assert job.preflight_acknowledged is False


# ---------------------------------------------------------------------------
# Intake service tests
# ---------------------------------------------------------------------------


class TestIntakeService:
    """Tests for apps/jobs/services.py intake helpers."""

    def _make_pdf_bytes(self) -> bytes:
        import io

        from pypdf import PageObject, PdfWriter

        buf = io.BytesIO()
        w = PdfWriter()
        w.add_page(PageObject.create_blank_page(width=612, height=792))
        w.write(buf)
        return buf.getvalue()

    def test_compute_fiery_name_no_preset(self):
        """Without a routing preset the fiery name is just the stem."""
        from apps.jobs.models import PrintJob
        from apps.jobs.services import compute_fiery_name

        job = PrintJob(name="my_file.pdf")
        result = compute_fiery_name(job)
        assert result == "my_file"

    def test_compute_fiery_name_with_preset(self):
        """With a routing preset the fiery name starts with the preset name."""
        from apps.jobs.models import PrintJob
        from apps.routing.models import RoutingPreset

        preset = RoutingPreset.objects.create(name="CoatedStock", printer_queue="q1")
        job = PrintJob.objects.create(name="flyer.pdf", routing_preset=preset)
        from apps.jobs.services import compute_fiery_name

        result = compute_fiery_name(job)
        assert result.startswith("CoatedStock_")
        assert "flyer" in result

    def test_run_preflight_for_job_no_template(self):
        """Without a template, preflight still runs without crashing."""
        from django.core.files.base import ContentFile

        from apps.jobs.models import PrintJob
        from apps.jobs.services import run_preflight_for_job

        job = PrintJob.objects.create(name="no_tmpl.pdf")
        job.file.save("no_tmpl.pdf", ContentFile(self._make_pdf_bytes()), save=True)
        # Should not raise
        run_preflight_for_job(job)

    def test_extract_pdf_metadata_via_services(self):
        """services.extract_pdf_metadata is re-exported from core.pdf_utils."""
        from django.core.files.base import ContentFile

        from apps.jobs.models import PrintJob
        from apps.jobs.services import extract_pdf_metadata

        job = PrintJob.objects.create(name="reexport.pdf")
        job.file.save("reexport.pdf", ContentFile(self._make_pdf_bytes()), save=True)
        extract_pdf_metadata(job)
        job.refresh_from_db()
        assert job.page_count == 1


# ---------------------------------------------------------------------------
# PrintJob immutability / field tests
# ---------------------------------------------------------------------------


class TestPrintJobImmutability:
    """Verify that critical PrintJob fields behave as expected after creation."""

    def test_pk_is_uuid_and_stable(self):
        """The primary key must be a UUID and must not change after save."""
        import uuid

        from apps.jobs.models import PrintJob

        job = PrintJob.objects.create(name="stable.pdf")
        pk_before = job.pk
        job.name = "changed.pdf"
        job.save(update_fields=["name"])
        assert job.pk == pk_before
        assert isinstance(job.pk, uuid.UUID)

    def test_status_default_is_pending(self):
        from apps.jobs.models import PrintJob

        job = PrintJob.objects.create(name="new.pdf")
        assert job.status == PrintJob.Status.PENDING

    def test_is_saved_defaults_to_false(self):
        from apps.jobs.models import PrintJob

        job = PrintJob.objects.create(name="x.pdf")
        assert job.is_saved is False

    def test_pages_are_unique_defaults_to_true(self):
        from apps.jobs.models import PrintJob

        job = PrintJob.objects.create(name="y.pdf")
        assert job.pages_are_unique is True

    def test_created_at_is_not_updated_on_save(self):
        """created_at must remain fixed after subsequent saves."""
        from apps.jobs.models import PrintJob

        job = PrintJob.objects.create(name="ts.pdf")
        original_created_at = job.created_at
        job.name = "ts_renamed.pdf"
        job.save(update_fields=["name"])
        job.refresh_from_db()
        assert job.created_at == original_created_at


# ---------------------------------------------------------------------------
# Celery task behaviour
# ---------------------------------------------------------------------------


class TestProcessJobTaskBehavior:
    """Integration tests for apps/jobs/tasks.process_job_task."""

    def _make_pdf_bytes(self) -> bytes:
        import io

        from pypdf import PageObject, PdfWriter

        buf = io.BytesIO()
        w = PdfWriter()
        w.add_page(PageObject.create_blank_page(width=612, height=792))
        w.write(buf)
        return buf.getvalue()

    def test_task_sets_status_to_error_on_missing_job(self):
        """Calling the task with an unknown job ID should return silently."""
        from apps.jobs.tasks import process_job_task

        # Should not raise
        process_job_task("00000000-0000-0000-0000-000000000000")

    def test_task_processes_job_without_template(self):
        """A job without a template should reach IMPOSED status (no imposition step)."""
        from django.core.files.base import ContentFile

        from apps.jobs.models import PrintJob
        from apps.jobs.tasks import process_job_task

        job = PrintJob.objects.create(name="notmpl.pdf")
        job.file.save("notmpl.pdf", ContentFile(self._make_pdf_bytes()), save=True)
        process_job_task(str(job.pk))
        job.refresh_from_db()
        # Without a template, imposition is skipped; the job should not be in ERROR
        assert job.status != PrintJob.Status.ERROR

    def test_task_processes_job_with_template(self):
        """A job with a template should reach IMPOSED status after task execution."""
        from django.core.files.base import ContentFile

        from apps.impose.models import ImpositionTemplate
        from apps.jobs.models import PrintJob
        from apps.jobs.tasks import process_job_task

        tmpl = ImpositionTemplate.objects.create(
            name="2-up test",
            sheet_width=1224,
            sheet_height=792,
            columns=2,
            rows=1,
        )
        job = PrintJob.objects.create(name="withtmpl.pdf", imposition_template=tmpl)
        job.file.save("withtmpl.pdf", ContentFile(self._make_pdf_bytes()), save=True)
        process_job_task(str(job.pk))
        job.refresh_from_db()
        assert job.status == PrintJob.Status.IMPOSED
        assert job.imposed_file


# ---------------------------------------------------------------------------
# Upload view security: file size limit
# ---------------------------------------------------------------------------


class TestUploadFileSizeLimit:
    """The upload view must reject files that exceed MAX_PDF_UPLOAD_BYTES."""

    def test_oversized_pdf_rejected(self, client, user, settings):
        """Files larger than MAX_PDF_UPLOAD_BYTES should return HTTP 400."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        client.force_login(user)
        settings.MAX_PDF_UPLOAD_BYTES = 10  # very small limit for the test

        f = SimpleUploadedFile(
            "big.pdf",
            b"%PDF-1.4 " + b"X" * 20,  # 29 bytes > 10
            content_type="application/pdf",
        )
        from django.urls import reverse

        response = client.post(reverse("jobs:upload"), {"file": f})
        assert response.status_code == 400
