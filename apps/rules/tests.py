import pytest

pytestmark = pytest.mark.django_db


class TestRuleModel:
    def test_create_rule(self):
        from apps.rules.models import Rule
        r = Rule.objects.create(
            name="Letter to 4-up",
            condition_type=Rule.ConditionType.PAGE_SIZE,
            condition_value="612x792",
            action_type=Rule.ActionType.APPLY_TEMPLATE,
            action_value="1",
        )
        assert "Letter to 4-up" in str(r)


class TestRulesEngine:
    def test_page_size_match(self):
        from apps.rules.engine import _matches
        from apps.rules.models import Rule

        rule = Rule(
            name="test",
            condition_type=Rule.ConditionType.PAGE_SIZE,
            condition_value="612x792",
            action_type=Rule.ActionType.APPLY_TEMPLATE,
            action_value="1",
        )

        class FakeJob:
            page_width = 612
            page_height = 792

        assert _matches(rule, FakeJob()) is True

    def test_page_size_no_match(self):
        from apps.rules.engine import _matches
        from apps.rules.models import Rule

        rule = Rule(
            name="test",
            condition_type=Rule.ConditionType.PAGE_SIZE,
            condition_value="612x792",
            action_type=Rule.ActionType.APPLY_TEMPLATE,
            action_value="1",
        )

        class FakeJob:
            page_width = 595
            page_height = 842

        assert _matches(rule, FakeJob()) is False

    def test_page_count_gte(self):
        from apps.rules.engine import _matches
        from apps.rules.models import Rule

        rule = Rule(
            name="test",
            condition_type=Rule.ConditionType.PAGE_COUNT,
            condition_value=">=4",
            action_type=Rule.ActionType.APPLY_TEMPLATE,
            action_value="1",
        )

        class FakeJob:
            page_count = 4

        assert _matches(rule, FakeJob()) is True

    def test_filename_pattern(self):
        from apps.rules.engine import _matches
        from apps.rules.models import Rule

        rule = Rule(
            name="test",
            condition_type=Rule.ConditionType.FILENAME,
            condition_value="*.pdf",
            action_type=Rule.ActionType.APPLY_TEMPLATE,
            action_value="1",
        )

        class FakeJob:
            name = "my_order.pdf"

        assert _matches(rule, FakeJob()) is True

    def test_apply_rules_assigns_template(self):
        from apps.impose.models import ImpositionTemplate
        from apps.jobs.models import PrintJob
        from apps.rules.engine import apply_rules
        from apps.rules.models import Rule

        tmpl = ImpositionTemplate.objects.create(
            name="4-Up",
            layout_type="4up",
            sheet_width=1224,
            sheet_height=792,
            columns=4,
            rows=1,
        )
        Rule.objects.create(
            name="Page size rule",
            condition_type=Rule.ConditionType.PAGE_SIZE,
            condition_value="612x792",
            action_type=Rule.ActionType.APPLY_TEMPLATE,
            action_value=str(tmpl.pk),
            priority=1,
        )
        job = PrintJob.objects.create(name="test.pdf", page_width=612, page_height=792)
        apply_rules(job)
        job.refresh_from_db()
        assert job.imposition_template_id == tmpl.pk
