from typing import Literal

from django.shortcuts import get_object_or_404
from ninja import Router, Schema

router = Router(tags=["impose"])

# Exact model enums: RoutingPreset.DuplexMode / PrintJob.FitMode.
DuplexMode = Literal["simplex", "duplex_long", "duplex_short"]
FitMode = Literal["cover", "center"]


class TemplateOut(Schema):
    """Imposition template details returned by the API."""

    id: int
    name: str
    sheet_width: float
    sheet_height: float
    columns: int
    rows: int

    class Config:
        from_attributes = True


class TemplateIn(Schema):
    """Fields required to create a new imposition template."""

    name: str
    sheet_width: float
    sheet_height: float
    bleed: float = 0.0
    columns: int = 1
    rows: int = 1
    barcode_x: float | None = None
    barcode_y: float | None = None
    notes: str = ""


@router.get(
    "/templates", response=list[TemplateOut], summary="List imposition templates"
)
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


@router.post(
    "/templates", response=TemplateOut, summary="Create an imposition template"
)
def create_template(request, data: TemplateIn):
    """Create and persist a new imposition template."""
    from apps.impose.models import ImpositionTemplate

    return ImpositionTemplate.objects.create(**data.dict())


@router.post("/{job_id}/impose", summary="Queue imposition for a job")
def impose_job(
    request,
    job_id: str,
    template_id: int | None = None,
    duplex: DuplexMode | None = None,
    fit_mode: FitMode | None = None,
):
    """
    Enqueue the imposition task for *job_id*.  Optionally override the
    template with *template_id*.  Imposition only; never sends to a printer.

    Optional duplex (simplex / duplex_long / duplex_short) and fit_mode
    (cover / center) are saved on the job (is_double_sided / fit_mode)
    before imposing, so this and later re-imposition use them.
    """
    from apps.impose.tasks import impose_job_task

    if duplex is not None or fit_mode is not None:
        from apps.jobs.models import PrintJob

        job = get_object_or_404(PrintJob, pk=job_id)
        fields = []
        if duplex is not None:
            job.is_double_sided = duplex != "simplex"
            fields.append("is_double_sided")
        if fit_mode is not None:
            job.fit_mode = fit_mode
            fields.append("fit_mode")
        job.save(update_fields=fields)

    impose_job_task.delay(job_id, template_id)
    return {
        "queued": True,
        "job_id": job_id,
        "template_id": template_id,
        "duplex": duplex,
        "fit_mode": fit_mode,
    }
