from ninja import Router, Schema

router = Router(tags=["rules"])


class RuleOut(Schema):
    """Ruleset details returned by the API."""

    id: int
    name: str
    imposition_template_id: int | None = None
    cutter_program_id: int | None = None
    routing_preset_id: int | None = None
    cut_size_id: int | None = None
    sheet_size_id: int | None = None
    product_category_id: int | None = None
    active: bool

    class Config:
        from_attributes = True


class RuleIn(Schema):
    """Fields required to create a ruleset."""

    name: str
    imposition_template_id: int | None = None
    cutter_program_id: int | None = None
    routing_preset_id: int | None = None
    cut_size_id: int | None = None
    sheet_size_id: int | None = None
    product_category_id: int | None = None


@router.get("/", response=list[RuleOut], summary="List all rulesets")
def list_rules(request):
    """Return all rulesets."""
    from apps.rules.models import Rule

    return list(Rule.objects.all())


@router.post("/", response=RuleOut, summary="Create a ruleset")
def create_rule(request, data: RuleIn):
    """Create and persist a new ruleset."""
    from apps.rules.models import Rule

    return Rule.objects.create(**data.dict())
