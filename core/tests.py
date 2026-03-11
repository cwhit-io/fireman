import json

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestIndexView:
    def test_index_returns_200(self, client: Client):
        response = client.get(reverse("core:index"))
        assert response.status_code == 200


class TestNinjaAPI:
    def test_hello_endpoint(self, client: Client):
        response = client.get("/api/hello")
        assert response.status_code == 200
        assert response.json()["message"] == "Hello from Django Ninja!"


class TestUserModel:
    def test_create_user(self, django_user_model):
        user = django_user_model.objects.create_user(
            username="alice", email="alice@example.com", password="pass"
        )
        assert user.pk is not None
        assert str(user) == "alice@example.com"

    def test_user_str_falls_back_to_username(self, django_user_model):
        user = django_user_model.objects.create_user(username="bob", password="pass")
        user.email = ""
        assert str(user) == "bob"


class TestPdfUtils:
    """Tests for core/pdf_utils.py."""

    def _make_minimal_pdf(self) -> bytes:
        return (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
            b"0000000058 00000 n\n0000000115 00000 n\n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
        )

    def test_validate_and_repair_clean_pdf(self):
        """A well-formed PDF should be returned unchanged with no warnings."""
        import io

        from django.core.files.base import ContentFile
        from pypdf import PageObject, PdfWriter

        from apps.jobs.models import PrintJob
        from core.pdf_utils import validate_and_repair_pdf

        buf = io.BytesIO()
        w = PdfWriter()
        w.add_page(PageObject.create_blank_page(width=612, height=792))
        w.write(buf)

        job = PrintJob.objects.create(name="clean.pdf")
        job.file.save("clean.pdf", ContentFile(buf.getvalue()), save=True)
        repaired, warnings = validate_and_repair_pdf(job.file)
        assert repaired is not None
        assert warnings == []

    def test_validate_and_repair_garbage_bytes(self):
        """Unreadable bytes should return None with a non-empty warnings list."""
        from django.core.files.base import ContentFile

        from apps.jobs.models import PrintJob
        from core.pdf_utils import validate_and_repair_pdf

        job = PrintJob.objects.create(name="bad.pdf")
        job.file.save("bad.pdf", ContentFile(b"NOT_A_PDF"), save=True)
        repaired, warnings = validate_and_repair_pdf(job.file)
        assert repaired is None
        assert len(warnings) > 0

    def test_extract_pdf_metadata_sets_fields(self):
        """extract_pdf_metadata must populate page_count, page_width, page_height."""
        from django.core.files.base import ContentFile

        from apps.jobs.models import PrintJob
        from core.pdf_utils import extract_pdf_metadata

        job = PrintJob.objects.create(name="meta.pdf")
        job.file.save("meta.pdf", ContentFile(self._make_minimal_pdf()), save=True)
        extract_pdf_metadata(job)
        job.refresh_from_db()
        assert job.page_count == 1
        assert float(job.page_width) == pytest.approx(612.0)
        assert float(job.page_height) == pytest.approx(792.0)

    def test_extract_pdf_metadata_error_path(self):
        """Corrupted file must set status=ERROR and populate error_message."""
        from django.core.files.base import ContentFile

        from apps.jobs.models import PrintJob
        from core.pdf_utils import extract_pdf_metadata

        job = PrintJob.objects.create(name="corrupt.pdf")
        job.file.save("corrupt.pdf", ContentFile(b"GARBAGE"), save=True)
        extract_pdf_metadata(job)
        job.refresh_from_db()
        assert job.status == PrintJob.Status.ERROR
        assert job.error_message != ""


class TestJobStatusConsumer:
    """Async tests for core/consumers.py JobStatusConsumer."""

    async def test_connect_and_receive_update(self):
        """Consumer must accept connections and relay job_status_update events."""
        import uuid

        from channels.layers import get_channel_layer
        from channels.testing import WebsocketCommunicator

        from config.asgi import application

        job_id = str(uuid.uuid4())
        communicator = WebsocketCommunicator(
            application, f"/ws/jobs/{job_id}/",
            headers=[(b"origin", b"http://localhost")],
        )
        connected, _ = await communicator.connect()
        assert connected

        channel_layer = get_channel_layer()
        group_name = f"job_status_{job_id}"
        await channel_layer.group_send(
            group_name,
            {
                "type": "job_status_update",
                "job_id": job_id,
                "status": "imposed",
                "progress": 100,
                "timestamp": "2024-01-01T00:00:00+00:00",
            },
        )

        response = await communicator.receive_from()
        data = json.loads(response)
        assert data["job_id"] == job_id
        assert data["status"] == "imposed"
        assert data["progress"] == 100

        await communicator.disconnect()

    async def test_disconnect_removes_from_group(self):
        """Disconnecting must not raise errors."""
        import uuid

        from channels.testing import WebsocketCommunicator

        from config.asgi import application

        job_id = str(uuid.uuid4())
        communicator = WebsocketCommunicator(
            application, f"/ws/jobs/{job_id}/",
            headers=[(b"origin", b"http://localhost")],
        )
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_message_format_has_timestamp(self):
        """job_status_update messages without a timestamp get one auto-filled."""
        import uuid

        from channels.layers import get_channel_layer
        from channels.testing import WebsocketCommunicator

        from config.asgi import application

        job_id = str(uuid.uuid4())
        communicator = WebsocketCommunicator(
            application, f"/ws/jobs/{job_id}/",
            headers=[(b"origin", b"http://localhost")],
        )
        await communicator.connect()

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"job_status_{job_id}",
            {
                "type": "job_status_update",
                "job_id": job_id,
                "status": "processing",
                # no timestamp provided — consumer should fill it in
            },
        )

        response = await communicator.receive_from()
        data = json.loads(response)
        assert "timestamp" in data
        assert data["timestamp"]  # non-empty

        await communicator.disconnect()
