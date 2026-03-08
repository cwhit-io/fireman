from ninja import Router, Schema

router = Router(tags=["rules"])


class RuleOut(Schema):
    id: int
    name: str
    priority: int
    condition_type: str
    condition_value: str
    imposition_template_id: int | None = None
    cutter_program_id: int | None = None
    routing_preset_id: int | None = None
    active: bool

    class Config:
        from_attributes = True


class RuleIn(Schema):
    name: str
    priority: int = 10
    condition_type: str
    condition_value: str
    imposition_template_id: int | None = None
    cutter_program_id: int | None = None
    routing_preset_id: int | None = None


@router.get("/", response=list[RuleOut])
def list_rules(request):
    from apps.rules.models import Rule

    return list(Rule.objects.all())


@router.post("/", response=RuleOut)
def create_rule(request, data: RuleIn):
    from apps.rules.models import Rule

    return Rule.objects.create(**data.dict())
