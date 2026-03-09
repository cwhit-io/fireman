import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _make_rule(**kwargs):
    from apps.rules.models import Rule

    defaults = {
        "name": "Test Ruleset",
        "active": True,
    }
    defaults.update(kwargs)
    return Rule.objects.create(**defaults)


class TestRuleModel:
    def test_create_rule(self):
        from apps.rules.models import Rule

        r = Rule.objects.create(name="Letter to 4-up")
        assert "Letter to 4-up" in str(r)

    def test_rule_str(self):
        from apps.rules.models import Rule

        r = Rule(name="My Ruleset")
        assert str(r) == "My Ruleset"


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
            "imposition_template": str(tmpl.pk),
            "active": "on",
        }
        response = client.post(url, data)
        assert response.status_code == 302
        assert Rule.objects.filter(name="Invoice Ruleset").exists()

    def test_create_view_post_missing_name(self, client):
        url = reverse("rules:create")
        data = {
            "name": "",
        }
        response = client.post(url, data)
        assert response.status_code == 400
        assert b"Name is required" in response.content

    def test_create_view_no_actions_still_valid(self, client):
        """Rulesets no longer require an action to be set."""
        from apps.rules.models import Rule

        url = reverse("rules:create")
        data = {
            "name": "No Action Ruleset",
            "active": "on",
        }
        response = client.post(url, data)
        assert response.status_code == 302
        assert Rule.objects.filter(name="No Action Ruleset").exists()

    def test_edit_view_get(self, client):
        rule = _make_rule(name="Edit Me")
        url = reverse("rules:edit", args=[rule.pk])
        response = client.get(url)
        assert response.status_code == 200
        assert b"Edit Me" in response.content

    def test_edit_view_post_valid(self, client):
        from apps.impose.models import ImpositionTemplate

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
            "imposition_template": str(tmpl.pk),
            "active": "on",
        }
        response = client.post(url, data)
        assert response.status_code == 302
        rule.refresh_from_db()
        assert rule.name == "New Name"

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

    def test_size_category_filters_on_template_dropdown(self, client):
        """When cut_size/sheet_size/product_category are set they filter templates."""
        from apps.impose.models import ImpositionTemplate, PrintSize, ProductCategory

        cat = ProductCategory.objects.create(name="Business Cards")
        sz = PrintSize.objects.create(
            name="Business Card", width=252, height=144, size_type="cut"
        )
        ImpositionTemplate.objects.create(
            name="BC 21-up",
            layout_type="business_card",
            sheet_width=1224,
            sheet_height=792,
            columns=7,
            rows=3,
            product_category=cat,
            cut_size=sz,
        )
        ImpositionTemplate.objects.create(
            name="Postcard 4-up",
            layout_type="postcard",
            sheet_width=1224,
            sheet_height=792,
            columns=4,
            rows=1,
        )
        url = reverse("rules:create")
        # POST HTMX filter request
        response = client.post(
            url,
            {
                "csrfmiddlewaretoken": "dummy",
                "_filter_templates": "1",
                "product_category": str(cat.pk),
                "cut_size": "",
                "sheet_size": "",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"BC 21-up" in response.content
        assert b"Postcard 4-up" not in response.content
