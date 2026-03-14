"""
apps/impose/tests/test_template_parsing.py
Unit tests for apps/impose/utils.py — canonical template parser and renderer.
"""

from __future__ import annotations

import pytest

from apps.impose.utils import (
    TemplateLine,
    _LEGACY_FIELDS_TOP_TO_BOTTOM,
    parse_imposition_template,
    render_imposition_lines,
)


# ---------------------------------------------------------------------------
# parse_imposition_template
# ---------------------------------------------------------------------------


class TestParseImpositionTemplate:
    def test_empty_string_returns_empty(self):
        assert parse_imposition_template("") == []

    def test_none_equivalent_empty(self):
        # None is not valid per type hint, but callers may pass it via ``or ""``.
        assert parse_imposition_template("") == []

    def test_whitespace_only_returns_empty(self):
        assert parse_imposition_template("   \n  \n") == []

    def test_static_line(self):
        ast = parse_imposition_template("Hello World")
        assert len(ast) == 1
        assert ast[0].kind == "static"
        assert ast[0].raw == "Hello World"

    def test_blank_static_lines_dropped(self):
        ast = parse_imposition_template("line1\n\nline2")
        assert len(ast) == 2
        kinds = [l.kind for l in ast]
        assert kinds == ["static", "static"]

    def test_single_field_line(self):
        ast = parse_imposition_template("{name}")
        assert len(ast) == 1
        assert ast[0].kind == "field"
        assert ast[0].field == "name"

    def test_field_name_lowercased(self):
        ast = parse_imposition_template("{City-State-Zip}")
        assert ast[0].kind == "field"
        assert ast[0].field == "city-state-zip"

    def test_br_token(self):
        ast = parse_imposition_template("{br}")
        assert len(ast) == 1
        assert ast[0].kind == "br"
        assert ast[0].field == "br"

    def test_blank_token(self):
        ast = parse_imposition_template("{blank}")
        assert len(ast) == 1
        assert ast[0].kind == "br"
        assert ast[0].field == "blank"

    def test_br_case_insensitive(self):
        ast = parse_imposition_template("{BR}")
        assert ast[0].kind == "br"

    def test_mixed_line(self):
        ast = parse_imposition_template("{first} {last}")
        assert len(ast) == 1
        assert ast[0].kind == "mixed"
        assert set(ast[0].tokens) == {"first", "last"}

    def test_mixed_line_with_static_text(self):
        ast = parse_imposition_template("Attn: {name}")
        assert ast[0].kind == "mixed"
        assert ast[0].tokens == ["name"]

    def test_multiline_template(self):
        template = "{name}\n{company}\n{city-state-zip}"
        ast = parse_imposition_template(template)
        assert len(ast) == 3
        assert [l.field for l in ast] == ["name", "company", "city-state-zip"]

    def test_default_template(self):
        """The default address template must parse without errors."""
        template = (
            "{presorttrayid}\n"
            "{name}\n"
            "{company}\n"
            "{urbanization}\n"
            "{sec-primary street}\n"
            "{primary street}\n"
            "{city-state-zip}\n"
            "{encodedimbno}"
        )
        ast = parse_imposition_template(template)
        kinds = {l.kind for l in ast}
        assert kinds == {"field"}
        fields = [l.field for l in ast]
        assert "encodedimbno" in fields
        assert "name" in fields


# ---------------------------------------------------------------------------
# render_imposition_lines
# ---------------------------------------------------------------------------


class TestRenderImpositionLines:
    def _rec(self, **kwargs):
        return {k: v for k, v in kwargs.items()}

    def test_empty_ast_legacy_fallback(self):
        record = self._rec(
            name="John Doe",
            company="",
            **{"primary street": "123 Main St", "city-state-zip": "Springfield, IL 62701"},
        )
        lines = render_imposition_lines(record, [])
        # Legacy ordering: top→bottom = imbno, name, ..., city-state-zip
        # (fields present: name, primary street, city-state-zip)
        assert "John Doe" in lines
        assert "123 Main St" in lines
        assert "Springfield, IL 62701" in lines
        # city-state-zip must be last
        assert lines[-1] == "Springfield, IL 62701"
        # name must come before primary street
        assert lines.index("John Doe") < lines.index("123 Main St")

    def test_legacy_fallback_skips_empty_fields(self):
        record = self._rec(**{"city-state-zip": "Springfield, IL 62701"})
        lines = render_imposition_lines(record, [])
        assert lines == ["Springfield, IL 62701"]

    def test_legacy_fallback_top_to_bottom_ordering(self):
        """Legacy ordering is _LEGACY_FIELDS_TOP_TO_BOTTOM (top → bottom)."""
        record = {f: f.upper() for f in _LEGACY_FIELDS_TOP_TO_BOTTOM}
        lines = render_imposition_lines(record, [])
        expected = [f.upper() for f in _LEGACY_FIELDS_TOP_TO_BOTTOM]
        assert lines == expected

    def test_static_line_always_included(self):
        ast = parse_imposition_template("ATTN: Resident")
        lines = render_imposition_lines({}, ast)
        assert lines == ["ATTN: Resident"]

    def test_field_line_with_value(self):
        ast = parse_imposition_template("{name}")
        lines = render_imposition_lines({"name": "Jane Smith"}, ast)
        assert lines == ["Jane Smith"]

    def test_field_line_missing_value_skipped(self):
        ast = parse_imposition_template("{name}")
        lines = render_imposition_lines({}, ast)
        assert lines == []

    def test_field_line_empty_value_skipped(self):
        ast = parse_imposition_template("{name}")
        lines = render_imposition_lines({"name": ""}, ast)
        assert lines == []

    def test_field_line_whitespace_only_skipped(self):
        ast = parse_imposition_template("{name}")
        lines = render_imposition_lines({"name": "   "}, ast)
        assert lines == []

    def test_br_produces_empty_string(self):
        ast = parse_imposition_template("{name}\n{br}\n{city-state-zip}")
        record = {"name": "Alice", "city-state-zip": "Boston, MA 02101"}
        lines = render_imposition_lines(record, ast)
        assert lines == ["Alice", "", "Boston, MA 02101"]

    def test_blank_produces_empty_string(self):
        ast = parse_imposition_template("{blank}")
        lines = render_imposition_lines({}, ast)
        assert lines == [""]

    def test_encodedimbno_always_filtered(self):
        ast = parse_imposition_template("{name}\n{encodedimbno}\n{city-state-zip}")
        record = {
            "name": "Bob",
            "encodedimbno": "SOMEBARCODE",
            "city-state-zip": "Austin, TX 78701",
        }
        lines = render_imposition_lines(record, ast)
        assert "SOMEBARCODE" not in lines
        assert lines == ["Bob", "Austin, TX 78701"]

    def test_encodedimbno_case_insensitive_filtered(self):
        """Template token {EncodedImbNo} is filtered regardless of case."""
        ast = parse_imposition_template("{EncodedImbNo}")
        record = {"encodedimbno": "BARCODE123"}
        lines = render_imposition_lines(record, ast)
        assert lines == []

    def test_case_insensitive_field_lookup(self):
        ast = parse_imposition_template("{City-State-Zip}")
        # After parsing, field is lowercased; record key must also be lowercase
        lines = render_imposition_lines({"city-state-zip": "Denver, CO 80201"}, ast)
        assert lines == ["Denver, CO 80201"]

    def test_mixed_line_substitution(self):
        ast = parse_imposition_template("{first} {last}")
        lines = render_imposition_lines({"first": "Jane", "last": "Doe"}, ast)
        assert lines == ["Jane Doe"]

    def test_mixed_line_empty_result_skipped(self):
        ast = parse_imposition_template("{first} {last}")
        lines = render_imposition_lines({}, ast)
        assert lines == []

    def test_mixed_line_partial_substitution(self):
        ast = parse_imposition_template("Attn: {name}")
        lines = render_imposition_lines({}, ast)
        # After substitution: "Attn: " → stripped → "Attn:" → non-empty → included
        assert lines == ["Attn:"]

    def test_top_to_bottom_ordering(self):
        template = "{name}\n{company}\n{city-state-zip}"
        ast = parse_imposition_template(template)
        record = {
            "name": "Alice",
            "company": "Acme Corp",
            "city-state-zip": "Portland, OR 97201",
        }
        lines = render_imposition_lines(record, ast)
        assert lines == ["Alice", "Acme Corp", "Portland, OR 97201"]

    def test_skip_fields_presorttrayid(self):
        ast = parse_imposition_template("{presorttrayid}\n{name}")
        record = {"presorttrayid": "TRAY01", "name": "Alice"}
        lines = render_imposition_lines(
            record, ast, skip_fields=frozenset({"presorttrayid"})
        )
        assert lines == ["Alice"]
        assert "TRAY01" not in lines

    def test_skip_fields_does_not_affect_encodedimbno_filter(self):
        """encodedimbno is always filtered even without skip_fields."""
        ast = parse_imposition_template("{encodedimbno}")
        record = {"encodedimbno": "BARCODE"}
        lines = render_imposition_lines(record, ast)
        assert lines == []

    def test_full_default_template(self):
        """Render a full address with the default template, check ordering."""
        template = (
            "{presorttrayid}\n"
            "{name}\n"
            "{company}\n"
            "{urbanization}\n"
            "{sec-primary street}\n"
            "{primary street}\n"
            "{city-state-zip}\n"
            "{encodedimbno}"
        )
        ast = parse_imposition_template(template)
        record = {
            "presorttrayid": "TRAY01",
            "name": "John Doe",
            "company": "",
            "urbanization": "",
            "sec-primary street": "",
            "primary street": "456 Elm St",
            "city-state-zip": "Chicago, IL 60601",
            "encodedimbno": "BARCODE999",
        }
        lines = render_imposition_lines(
            record, ast, skip_fields=frozenset({"presorttrayid"})
        )
        # presorttrayid and encodedimbno filtered, empty fields skipped
        assert lines == ["John Doe", "456 Elm St", "Chicago, IL 60601"]

    def test_legacy_fallback_skip_fields_respected(self):
        record = {"name": "Alice", "imbno": "999", "city-state-zip": "LA, CA 90001"}
        lines = render_imposition_lines(record, [], skip_fields=frozenset({"imbno"}))
        assert "999" not in lines
        assert "Alice" in lines
