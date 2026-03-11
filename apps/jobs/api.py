import uuid

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.files import UploadedFile

router = Router(tags=["jobs"])


class PrintJobOut(Schema):
    """Representation of a PrintJob returned by the API."""

    id: uuid.UUID
    name: str
    status: str
    page_count: int | None = None
    page_width: float | None = None
    page_height: float | None = None
    product_type: str
    error_message: str

    class Config:
        from_attributes = True


class PrintJobIn(Schema):
    """Fields accepted when creating or updating a PrintJob."""

    name: str = ""
    product_type: str = ""
    notes: str = ""


@router.get("/", response=list[PrintJobOut], summary="List all print jobs")
def list_jobs(request):
    """Return the most recent 100 print jobs ordered by creation date."""
    from apps.jobs.models import PrintJob

    return list(PrintJob.objects.all()[:100])


@router.get("/{job_id}", response=PrintJobOut, summary="Get a single print job")
def get_job(request, job_id: uuid.UUID):
    """Return details for the print job identified by *job_id*."""
    from apps.jobs.models import PrintJob

    return get_object_or_404(PrintJob, pk=job_id)


@router.post("/upload", response=PrintJobOut, summary="Upload a PDF and create a job")
def upload_job(request, file: UploadedFile, name: str = "", product_type: str = ""):
    """
    Accept a PDF file upload, persist it as a new PrintJob, and enqueue
    the processing pipeline (metadata extraction + imposition).
    """
    from apps.jobs.models import PrintJob
    from apps.jobs.tasks import process_job_task

    job = PrintJob.objects.create(
        name=name or file.name,
        file=file,
        product_type=product_type,
    )
    process_job_task.delay(str(job.pk))
    return job


@router.delete("/{job_id}", summary="Delete a print job")
def delete_job(request, job_id: uuid.UUID):
    """Permanently delete the print job and its associated files."""
    from apps.jobs.models import PrintJob

    job = get_object_or_404(PrintJob, pk=job_id)
    job.delete()
    return {"success": True}
