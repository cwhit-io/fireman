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


# ── Retired web CRUD views (redirect to /) ───────────────────────────────


class TestRetiredCutterRoutes:
    def test_list_redirects_to_home(self, client):
        response = client.get(reverse("cutter:list"))
        assert response.status_code == 302
        assert response["Location"] == "/"

    def test_create_redirects_to_home(self, client):
        response = client.get(reverse("cutter:create"))
        assert response.status_code == 302
        assert response["Location"] == "/"

    def test_edit_redirects_to_home(self, client):
        prog = _make_program(name="Existing", duplo_code="010")
        response = client.get(reverse("cutter:edit", kwargs={"pk": prog.pk}))
        assert response.status_code == 302
        assert response["Location"] == "/"

    def test_delete_redirects_to_home(self, client):
        prog = _make_program(name="Existing", duplo_code="010")
        response = client.get(reverse("cutter:delete", kwargs={"pk": prog.pk}))
        assert response.status_code == 302
        assert response["Location"] == "/"
