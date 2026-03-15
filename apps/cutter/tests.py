import pytest
from django.urls import reverse

from apps.cutter.models import CutterProgram

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_program(**kwargs) -> CutterProgram:
    defaults = {"name": "Test Program", "duplo_code": "001", "active": True}
    defaults.update(kwargs)
    return CutterProgram.objects.create(**defaults)


# ── Model ─────────────────────────────────────────────────────────────────


class TestCutterProgramModel:
    def test_str(self):
        p = _make_program(name="BC Standard", duplo_code="BC001")
        assert str(p) == "BC Standard (BC001)"

    def test_default_active(self):
        p = _make_program()
        assert p.active is True

    def test_barcode_dimensions_default(self):
        p = _make_program()
        assert float(p.barcode_width) == pytest.approx(90.0)
        assert float(p.barcode_height) == pytest.approx(25.2)

    def test_barcode_position_optional(self):
        p = _make_program()
        assert p.barcode_x is None
        assert p.barcode_y is None

    def test_ordering_by_name(self):
        _make_program(name="Zzz", duplo_code="099")
        _make_program(name="Aaa", duplo_code="002")
        names = list(CutterProgram.objects.values_list("name", flat=True))
        assert names == sorted(names)


# ── List view ─────────────────────────────────────────────────────────────


class TestProgramListView:
    def test_get_returns_200(self, client):
        response = client.get(reverse("cutter:list"))
        assert response.status_code == 200

    def test_shows_programs(self, client):
        _make_program(name="Bookmark", duplo_code="023")
        response = client.get(reverse("cutter:list"))
        assert b"Bookmark" in response.content

    def test_sort_by_name(self, client):
        _make_program(name="Zebra", duplo_code="003")
        _make_program(name="Alpha", duplo_code="002")
        response = client.get(reverse("cutter:list") + "?sort=name")
        assert response.status_code == 200
        content = response.content.decode()
        assert content.index("Alpha") < content.index("Zebra")

    def test_sort_by_name_descending(self, client):
        _make_program(name="Zebra", duplo_code="003")
        _make_program(name="Alpha", duplo_code="002")
        response = client.get(reverse("cutter:list") + "?sort=-name")
        assert response.status_code == 200
        content = response.content.decode()
        assert content.index("Zebra") < content.index("Alpha")

    def test_sort_by_duplo_code(self, client):
        _make_program(name="Z", duplo_code="099")
        _make_program(name="A", duplo_code="002")
        response = client.get(reverse("cutter:list") + "?sort=duplo_code")
        assert response.status_code == 200
        content = response.content.decode()
        assert content.index("002") < content.index("099")

    def test_invalid_sort_falls_back(self, client):
        response = client.get(reverse("cutter:list") + "?sort=evil_field")
        assert response.status_code == 200


# ── Create view ───────────────────────────────────────────────────────────


class TestProgramCreateView:
    def test_get_returns_200(self, client):
        response = client.get(reverse("cutter:create"))
        assert response.status_code == 200

    def test_post_valid_creates_program(self, client):
        response = client.post(
            reverse("cutter:create"),
            {
                "name": "New Program",
                "duplo_code": "042",
                "description": "Test desc",
                "active": "on",
                "barcode_width": "90.0",
                "barcode_height": "25.2",
            },
        )
        assert response.status_code == 302
        assert CutterProgram.objects.filter(name="New Program").exists()

    def test_post_valid_redirects_to_list(self, client):
        response = client.post(
            reverse("cutter:create"),
            {
                "name": "X",
                "duplo_code": "002",
                "barcode_width": "90",
                "barcode_height": "25.2",
            },
        )
        assert response["Location"] == reverse("cutter:list")

    def test_post_missing_name_returns_400(self, client):
        response = client.post(
            reverse("cutter:create"),
            {
                "name": "",
                "duplo_code": "001",
                "barcode_width": "90",
                "barcode_height": "25.2",
            },
        )
        assert response.status_code == 400

    def test_post_missing_duplo_code_returns_400(self, client):
        response = client.post(
            reverse("cutter:create"),
            {
                "name": "Valid Name",
                "duplo_code": "",
                "barcode_width": "90",
                "barcode_height": "25.2",
            },
        )
        assert response.status_code == 400

    def test_post_inactive_when_active_omitted(self, client):
        client.post(
            reverse("cutter:create"),
            {
                "name": "Inactive",
                "duplo_code": "099",
                "barcode_width": "90",
                "barcode_height": "25.2",
            },
        )
        p = CutterProgram.objects.get(name="Inactive")
        assert p.active is False

    def test_post_with_barcode_position(self, client):
        client.post(
            reverse("cutter:create"),
            {
                "name": "WithPos",
                "duplo_code": "010",
                "barcode_x": "18.0",
                "barcode_y": "36.0",
                "barcode_width": "90.0",
                "barcode_height": "25.2",
            },
        )
        p = CutterProgram.objects.get(name="WithPos")
        assert float(p.barcode_x) == pytest.approx(18.0)
        assert float(p.barcode_y) == pytest.approx(36.0)


# ── Edit view ─────────────────────────────────────────────────────────────


class TestProgramEditView:
    def test_get_returns_200(self, client):
        p = _make_program()
        response = client.get(reverse("cutter:edit", kwargs={"pk": p.pk}))
        assert response.status_code == 200

    def test_get_404_for_missing(self, client):
        response = client.get(reverse("cutter:edit", kwargs={"pk": 9999}))
        assert response.status_code == 404

    def test_get_prepopulates_values(self, client):
        p = _make_program(name="Existing", duplo_code="005")
        response = client.get(reverse("cutter:edit", kwargs={"pk": p.pk}))
        assert b"Existing" in response.content
        assert b"005" in response.content

    def test_post_valid_updates_program(self, client):
        p = _make_program(name="Old Name", duplo_code="001")
        client.post(
            reverse("cutter:edit", kwargs={"pk": p.pk}),
            {
                "name": "New Name",
                "duplo_code": "002",
                "description": "Updated",
                "active": "on",
                "barcode_width": "90.0",
                "barcode_height": "25.2",
            },
        )
        p.refresh_from_db()
        assert p.name == "New Name"
        assert p.duplo_code == "002"

    def test_post_valid_redirects_to_list(self, client):
        p = _make_program()
        response = client.post(
            reverse("cutter:edit", kwargs={"pk": p.pk}),
            {
                "name": "X",
                "duplo_code": "001",
                "barcode_width": "90",
                "barcode_height": "25.2",
            },
        )
        assert response["Location"] == reverse("cutter:list")

    def test_post_missing_name_returns_400(self, client):
        p = _make_program()
        response = client.post(
            reverse("cutter:edit", kwargs={"pk": p.pk}),
            {
                "name": "",
                "duplo_code": "001",
                "barcode_width": "90",
                "barcode_height": "25.2",
            },
        )
        assert response.status_code == 400

    def test_post_clears_barcode_position_when_blank(self, client):
        from decimal import Decimal

        p = _make_program(barcode_x=Decimal("18"), barcode_y=Decimal("36"))
        client.post(
            reverse("cutter:edit", kwargs={"pk": p.pk}),
            {
                "name": p.name,
                "duplo_code": p.duplo_code,
                "active": "on",
                "barcode_x": "",
                "barcode_y": "",
                "barcode_width": "90.0",
                "barcode_height": "25.2",
            },
        )
        p.refresh_from_db()
        assert p.barcode_x is None
        assert p.barcode_y is None

    def test_post_deactivates_program(self, client):
        p = _make_program(active=True)
        client.post(
            reverse("cutter:edit", kwargs={"pk": p.pk}),
            {
                "name": p.name,
                "duplo_code": p.duplo_code,
                "barcode_width": "90",
                "barcode_height": "25.2",
            },
        )
        p.refresh_from_db()
        assert p.active is False


# ── Delete view ───────────────────────────────────────────────────────────


class TestProgramDeleteView:
    def test_get_confirm_page(self, client):
        p = _make_program()
        response = client.get(reverse("cutter:delete", kwargs={"pk": p.pk}))
        assert response.status_code == 200
        assert p.name.encode() in response.content

    def test_get_404_for_missing(self, client):
        response = client.get(reverse("cutter:delete", kwargs={"pk": 9999}))
        assert response.status_code == 404

    def test_post_deletes_program(self, client):
        p = _make_program()
        pk = p.pk
        client.post(reverse("cutter:delete", kwargs={"pk": pk}))
        assert not CutterProgram.objects.filter(pk=pk).exists()

    def test_post_redirects_to_list(self, client):
        p = _make_program()
        response = client.post(reverse("cutter:delete", kwargs={"pk": p.pk}))
        assert response["Location"] == reverse("cutter:list")


# ── Barcode view ──────────────────────────────────────────────────────────


class TestProgramBarcodeView:
    def test_barcode_endpoint_404_for_missing_program(self, client):
        response = client.get(reverse("cutter:barcode", kwargs={"pk": 9999}))
        assert response.status_code == 404

    def test_barcode_endpoint_404_for_non_numeric_code(self, client):
        """Programs with non-numeric duplo_code have no TIF → 404."""
        p = _make_program(duplo_code="NOT_A_NUMBER")
        response = client.get(reverse("cutter:barcode", kwargs={"pk": p.pk}))
        assert response.status_code == 404

    def test_barcode_endpoint_404_when_tif_missing(self, client):
        """Numeric duplo_code but TIF file doesn't exist on disk → 404."""
        p = _make_program(duplo_code="999")
        response = client.get(reverse("cutter:barcode", kwargs={"pk": p.pk}))
        assert response.status_code == 404


# ── API ───────────────────────────────────────────────────────────────────


class TestCutterProgramApi:
    def test_list_returns_only_active(self, client):
        _make_program(name="Active", duplo_code="001", active=True)
        _make_program(name="Inactive", duplo_code="002", active=False)
        response = client.get("/api/cutter/programs")
        assert response.status_code == 200
        names = [p["name"] for p in response.json()]
        assert "Active" in names
        assert "Inactive" not in names

    def test_list_empty(self, client):
        response = client.get("/api/cutter/programs")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_program_via_api(self, client):
        response = client.post(
            "/api/cutter/programs",
            {"name": "Via API", "duplo_code": "010", "description": "Test"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert CutterProgram.objects.filter(name="Via API").exists()
