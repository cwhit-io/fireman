import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _make_rule(**kwargs):
    from apps.rules.models import Rule

    defaults = {
        "name": "Test Ruleset",
        "condition_type": Rule.ConditionType.PAGE_SIZE,
        "condition_value": "8.5x11",
        "priority": 10,
        "active": True,
    }
    defaults.update(kwargs)
    return Rule.objects.create(**defaults)


class TestRuleModel:
    def test_create_rule(self):
        from apps.rules.models import Rule

        r = Rule.objects.create(
            name="Letter to 4-up",
            condition_type=Rule.ConditionType.PAGE_SIZE,
            condition_value="8.5x11",
        )
        assert "Letter to 4-up" in str(r)


class TestRulesEngine:
    def test_page_size_match(self):
        from apps.rules.engine import _matches
        from apps.rules.models import Rule

        rule = Rule(
            name="test",
            condition_type=Rule.ConditionType.PAGE_SIZE,
            condition_value="8.5x11",
        )

        class FakeJob:
            page_width = 612  # 8.5 * 72
            page_height = 792  # 11 * 72

        assert _matches(rule, FakeJob()) is True

    def test_page_size_no_match(self):
        from apps.rules.engine import _matches
        from apps.rules.models import Rule

        rule = Rule(
            name="test",
            condition_type=Rule.ConditionType.PAGE_SIZE,
            condition_value="8.5x11",
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
            condition_value="8.5x11",
            imposition_template=tmpl,
            priority=1,
        )
        job = PrintJob.objects.create(name="test.pdf", page_width=612, page_height=792)
        apply_rules(job)
        job.refresh_from_db()
        assert job.imposition_template_id == tmpl.pk

    def test_apply_rules_assigns_all_actions(self):
        from apps.cutter.models import CutterProgram
        from apps.impose.models import ImpositionTemplate
        from apps.jobs.models import PrintJob
        from apps.routing.models import RoutingPreset
        from apps.rules.engine import apply_rules
        from apps.rules.models import Rule

        tmpl = ImpositionTemplate.objects.create(
            name="4-Up Multi",
            layout_type="4up",
            sheet_width=1224,
            sheet_height=792,
            columns=4,
            rows=1,
        )
        cutter = CutterProgram.objects.create(name="Prog1", duplo_code="P001")
        preset = RoutingPreset.objects.create(name="Fiery Color", printer_queue="fiery")
        Rule.objects.create(
            name="Full ruleset",
            condition_type=Rule.ConditionType.PAGE_SIZE,
            condition_value="8.5x11",
            imposition_template=tmpl,
            cutter_program=cutter,
            routing_preset=preset,
            priority=1,
        )
        job = PrintJob.objects.create(name="test.pdf", page_width=612, page_height=792)
        apply_rules(job)
        job.refresh_from_db()
        assert job.imposition_template_id == tmpl.pk
        assert job.cutter_program_id == cutter.pk
        assert job.routing_preset_id == preset.pk


class TestRuleViews:
    def test_list_view(self, client):
        _make_rule(name="My Ruleset")
        url = reverse("rules:list")
        response = client.get(url)
        assert response.status_code == 200
        assert b"My Ruleset" in response.content

    def test_list_view_empty(self, client):
        url = reverse("rules:list")
        response = client.get(url)
        assert response.status_code == 200
        assert b"No rulesets defined" in response.content

    def test_create_view_get(self, client):
        url = reverse("rules:create")
        response = client.get(url)
        assert response.status_code == 200
        assert b"New Ruleset" in response.content

    def test_create_view_post_valid(self, client):
        from apps.impose.models import ImpositionTemplate
        from apps.rules.models import Rule

        tmpl = ImpositionTemplate.objects.create(
            name="Test Tmpl",
            layout_type="4up",
            sheet_width=1224,
            sheet_height=792,
            columns=4,
            rows=1,
        )
        url = reverse("rules:create")
        data = {
            "name": "Invoice Ruleset",
            "priority": "5",
            "condition_type": Rule.ConditionType.FILENAME,
            "condition_value": "*invoice*",
            "imposition_template": str(tmpl.pk),
            "active": "on",
        }
        response = client.post(url, data)
        assert response.status_code == 302
        assert Rule.objects.filter(name="Invoice Ruleset").exists()

    def test_create_view_post_missing_name(self, client):
        from apps.impose.models import ImpositionTemplate
        from apps.rules.models import Rule

        tmpl = ImpositionTemplate.objects.create(
            name="Test Tmpl2",
            layout_type="4up",
            sheet_width=1224,
            sheet_height=792,
            columns=4,
            rows=1,
        )
        url = reverse("rules:create")
        data = {
            "name": "",
            "priority": "5",
            "condition_type": Rule.ConditionType.FILENAME,
            "condition_value": "*invoice*",
            "imposition_template": str(tmpl.pk),
        }
        response = client.post(url, data)
        assert response.status_code == 400
        assert b"Name is required" in response.content

    def test_create_view_post_missing_actions(self, client):
        from apps.rules.models import Rule

        url = reverse("rules:create")
        data = {
            "name": "No Action",
            "priority": "5",
            "condition_type": Rule.ConditionType.FILENAME,
            "condition_value": "*invoice*",
        }
        response = client.post(url, data)
        assert response.status_code == 400
        assert b"At least one action" in response.content

    def test_edit_view_get(self, client):
        rule = _make_rule(name="Edit Me")
        url = reverse("rules:edit", args=[rule.pk])
        response = client.get(url)
        assert response.status_code == 200
        assert b"Edit Me" in response.content

    def test_edit_view_post_valid(self, client):
        from apps.impose.models import ImpositionTemplate
        from apps.rules.models import Rule

        tmpl = ImpositionTemplate.objects.create(
            name="Edit Tmpl",
            layout_type="4up",
            sheet_width=1224,
            sheet_height=792,
            columns=4,
            rows=1,
        )
        rule = _make_rule(name="Old Name")
        url = reverse("rules:edit", args=[rule.pk])
        data = {
            "name": "New Name",
            "priority": "3",
            "condition_type": Rule.ConditionType.PAGE_SIZE,
            "condition_value": "8.5x11",
            "imposition_template": str(tmpl.pk),
            "active": "on",
        }
        response = client.post(url, data)
        assert response.status_code == 302
        rule.refresh_from_db()
        assert rule.name == "New Name"
        assert rule.priority == 3

    def test_delete_view_get(self, client):
        rule = _make_rule(name="Delete Me")
        url = reverse("rules:delete", args=[rule.pk])
        response = client.get(url)
        assert response.status_code == 200
        assert b"Delete Me" in response.content

    def test_delete_view_post(self, client):
        from apps.rules.models import Rule

        rule = _make_rule(name="Bye")
        pk = rule.pk
        url = reverse("rules:delete", args=[pk])
        response = client.post(url)
        assert response.status_code == 302
        assert not Rule.objects.filter(pk=pk).exists()

    def test_toggle_view_disables_active_rule(self, client):
        rule = _make_rule(active=True)
        url = reverse("rules:toggle", args=[rule.pk])
        response = client.post(url)
        assert response.status_code == 302
        rule.refresh_from_db()
        assert rule.active is False

    def test_toggle_view_enables_inactive_rule(self, client):
        rule = _make_rule(active=False)
        url = reverse("rules:toggle", args=[rule.pk])
        response = client.post(url)
        assert response.status_code == 302
        rule.refresh_from_db()
        assert rule.active is True
