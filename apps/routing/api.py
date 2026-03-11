from ninja import Router, Schema

router = Router(tags=["routing"])


class RoutingPresetOut(Schema):
    """Routing preset details returned by the API."""

    id: int
    name: str
    printer_queue: str
    duplex: str
    color_mode: str
    copies: int
    active: bool

    class Config:
        from_attributes = True


class RoutingPresetIn(Schema):
    """Fields required to create a routing preset."""

    name: str
    printer_queue: str = "fiery"
    media_type: str = ""
    media_size: str = ""
    duplex: str = "simplex"
    color_mode: str = "color"
    tray: str = ""
    copies: int = 1
    extra_lpr_options: str = ""


@router.get(
    "/presets", response=list[RoutingPresetOut], summary="List active routing presets"
)
def list_presets(request):
    """Return all active routing presets."""
    from apps.routing.models import RoutingPreset

    return list(RoutingPreset.objects.filter(active=True))


@router.post("/presets", response=RoutingPresetOut, summary="Create a routing preset")
def create_preset(request, data: RoutingPresetIn):
    """Create and persist a new routing preset."""
    from apps.routing.models import RoutingPreset

    return RoutingPreset.objects.create(**data.dict())


@router.post("/{job_id}/send", summary="Queue a job for sending to the printer")
def send_job(request, job_id: str):
    """Enqueue the send-to-printer task for *job_id*."""
    from apps.routing.tasks import send_job_task

    send_job_task.delay(job_id)
    return {"queued": True, "job_id": job_id}
