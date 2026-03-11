from django.shortcuts import get_object_or_404
from ninja import Router, Schema

router = Router(tags=["impose"])


class TemplateOut(Schema):
    """Imposition template details returned by the API."""

    id: int
    name: str
    layout_type: str
    sheet_width: float
    sheet_height: float
    columns: int
    rows: int

    class Config:
        from_attributes = True


class TemplateIn(Schema):
    """Fields required to create a new imposition template."""

    name: str
    layout_type: str
    sheet_width: float
    sheet_height: float
    bleed: float = 0.0
    margin_top: float = 0.0
    margin_right: float = 0.0
    margin_bottom: float = 0.0
    margin_left: float = 0.0
    columns: int = 1
    rows: int = 1
    barcode_x: float | None = None
    barcode_y: float | None = None
    notes: str = ""


@router.get("/templates", response=list[TemplateOut], summary="List imposition templates")
def list_templates(request):
    """Return all available imposition templates."""
    from apps.impose.models import ImpositionTemplate

    return list(ImpositionTemplate.objects.all())


@router.get(
    "/templates/{template_id}",
    response=TemplateOut,
    summary="Get a single imposition template",
)
def get_template(request, template_id: int):
    """Return details for the imposition template identified by *template_id*."""
    from apps.impose.models import ImpositionTemplate

    return get_object_or_404(ImpositionTemplate, pk=template_id)


@router.post("/templates", response=TemplateOut, summary="Create an imposition template")
def create_template(request, data: TemplateIn):
    """Create and persist a new imposition template."""
    from apps.impose.models import ImpositionTemplate

    return ImpositionTemplate.objects.create(**data.dict())


@router.post("/{job_id}/impose", summary="Queue imposition for a job")
def impose_job(request, job_id: str, template_id: int | None = None):
    """
    Enqueue the imposition task for *job_id*.  Optionally override the
    template with *template_id*.
    """
    from apps.impose.tasks import impose_job_task

    impose_job_task.delay(job_id, template_id)
    return {"queued": True, "job_id": job_id}
