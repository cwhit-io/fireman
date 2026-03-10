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

    def test_no_scaling(self):
        """Both generic CUPS and Fiery-native scale options must be disabled."""
        from apps.routing.models import RoutingPreset
        from apps.routing.services import _build_lpr_command

        preset = RoutingPreset(
            name="Scale Test",
            printer_queue="q",
            copies=1,
        )
        cmd_str = " ".join(_build_lpr_command(preset, "/tmp/x.pdf"))
        assert "fit-to-page=false" in cmd_str
        assert "EFScaleToFit=OFF" in cmd_str

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

    def test_duplex_override_fiery_options_uses_efduplex(self):
        """Duplex override must use EFDuplex for presets that use fiery_options."""
        from apps.routing.models import RoutingPreset
        from apps.routing.services import _build_lpr_command

        preset = RoutingPreset(
            name="Fiery Duplex",
            printer_queue="q",
            copies=1,
            fiery_options={"EFMediaType": "Coated"},
        )
        cmd_str = " ".join(
            _build_lpr_command(preset, "/tmp/x.pdf", duplex_override="duplex_long")
        )
        assert "EFDuplex=TopTop" in cmd_str
        assert "sides=" not in cmd_str

    def test_duplex_override_simplex_fiery_options(self):
        """Simplex override must send EFDuplex=False for Fiery presets."""
        from apps.routing.models import RoutingPreset
        from apps.routing.services import _build_lpr_command

        preset = RoutingPreset(
            name="Fiery Simplex",
            printer_queue="q",
            copies=1,
            fiery_options={"EFDuplex": "TopTop"},
        )
        cmd_str = " ".join(
            _build_lpr_command(preset, "/tmp/x.pdf", duplex_override="simplex")
        )
        assert "EFDuplex=False" in cmd_str
        assert "sides=" not in cmd_str

    def test_duplex_override_legacy_uses_sides(self):
        """Duplex override must use sides= for legacy presets (no fiery_options)."""
        from apps.routing.models import RoutingPreset
        from apps.routing.services import _build_lpr_command

        preset = RoutingPreset(
            name="Legacy Duplex",
            printer_queue="q",
            copies=1,
            fiery_options={},
        )
        cmd_str = " ".join(
            _build_lpr_command(preset, "/tmp/x.pdf", duplex_override="duplex_long")
        )
        assert "sides=two-sided-long-edge" in cmd_str
        assert "EFDuplex=" not in cmd_str

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
