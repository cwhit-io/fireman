from ninja import Router, Schema

router = Router(tags=["cutter"])


class CutterProgramOut(Schema):
    """Cutter program details returned by the API."""

    id: int
    name: str
    duplo_code: str
    description: str
    active: bool

    class Config:
        from_attributes = True


class CutterProgramIn(Schema):
    """Fields required to create a cutter program."""

    name: str
    duplo_code: str
    description: str = ""


@router.get("/programs", response=list[CutterProgramOut], summary="List active cutter programs")
def list_programs(request):
    """Return all active cutter programs."""
    from apps.cutter.models import CutterProgram

    return list(CutterProgram.objects.filter(active=True))


@router.post("/programs", response=CutterProgramOut, summary="Create a cutter program")
def create_program(request, data: CutterProgramIn):
    """Create and persist a new cutter program."""
    from apps.cutter.models import CutterProgram

    return CutterProgram.objects.create(**data.dict())
