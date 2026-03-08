import pytest

pytestmark = pytest.mark.django_db


class TestRoutingPresetModel:
    def test_create_preset(self):
        from apps.routing.models import RoutingPreset

        p = RoutingPreset.objects.create(name="Coated Stock", printer_queue="fiery_q1")
        assert str(p) == "Coated Stock"


class TestBuildLprCommand:
    def test_basic_command(self):
        from apps.routing.models import RoutingPreset
        from apps.routing.services import _build_lpr_command

        preset = RoutingPreset(
            name="Test",
            printer_queue="test_q",
            copies=2,
            duplex="simplex",
            color_mode="color",
        )
        cmd = _build_lpr_command(preset, "/tmp/test.pdf")
        assert "lpr" in cmd
        assert "-P" in cmd
        assert "test_q" in cmd
        assert "/tmp/test.pdf" in cmd

    def test_duplex_long_edge(self):
        from apps.routing.models import RoutingPreset
        from apps.routing.services import _build_lpr_command

        preset = RoutingPreset(
            name="Duplex Test",
            printer_queue="q",
            duplex="duplex_long",
            copies=1,
        )
        cmd = _build_lpr_command(preset, "/tmp/x.pdf")
        assert "two-sided-long-edge" in " ".join(cmd)

    def test_grayscale(self):
        from apps.routing.models import RoutingPreset
        from apps.routing.services import _build_lpr_command

        preset = RoutingPreset(
            name="Gray Test",
            printer_queue="q",
            color_mode="grayscale",
            duplex="simplex",
            copies=1,
        )
        cmd = _build_lpr_command(preset, "/tmp/x.pdf")
        assert "ColorModel=Gray" in " ".join(cmd)
