import uuid

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.files import UploadedFile

router = Router(tags=["jobs"])


class PrintJobOut(Schema):
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
    name: str = ""
    product_type: str = ""
    notes: str = ""


@router.get("/", response=list[PrintJobOut])
def list_jobs(request):
    from apps.jobs.models import PrintJob
    return list(PrintJob.objects.all()[:100])


@router.get("/{job_id}", response=PrintJobOut)
def get_job(request, job_id: uuid.UUID):
    from apps.jobs.models import PrintJob
    return get_object_or_404(PrintJob, pk=job_id)


@router.post("/upload", response=PrintJobOut)
def upload_job(request, file: UploadedFile, name: str = "", product_type: str = ""):
    from apps.jobs.models import PrintJob
    from apps.jobs.tasks import process_job_task

    job = PrintJob.objects.create(
        name=name or file.name,
        file=file,
        product_type=product_type,
    )
    process_job_task.delay(str(job.pk))
    return job


@router.delete("/{job_id}")
def delete_job(request, job_id: uuid.UUID):
    from apps.jobs.models import PrintJob
    job = get_object_or_404(PrintJob, pk=job_id)
    job.delete()
    return {"success": True}
