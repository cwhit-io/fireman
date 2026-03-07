from ninja import Router, Schema

router = Router(tags=["cutter"])


class CutterProgramOut(Schema):
    id: int
    name: str
    duplo_code: str
    description: str
    active: bool

    class Config:
        from_attributes = True


class CutterProgramIn(Schema):
    name: str
    duplo_code: str
    description: str = ""


@router.get("/programs", response=list[CutterProgramOut])
def list_programs(request):
    from apps.cutter.models import CutterProgram
    return list(CutterProgram.objects.filter(active=True))


@router.post("/programs", response=CutterProgramOut)
def create_program(request, data: CutterProgramIn):
    from apps.cutter.models import CutterProgram
    return CutterProgram.objects.create(**data.dict())
