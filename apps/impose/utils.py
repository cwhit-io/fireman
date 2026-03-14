"""
apps/impose/utils.py
Canonical server-side imposition template parser and renderer.
All server-side generation (gang-up, step-and-repeat, printjob builds) must call
render_imposition_lines() — do not parse templates inline elsewhere.

Token semantics must remain in sync with static/js/impose/template.js.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as _field
from typing import Literal

__all__ = [
    "TemplateLine",
    "parse_imposition_template",
    "render_imposition_lines",
]

_TOKEN_RE = re.compile(r"\{([^}]+)\}")

# Non-address special tokens always filtered from rendered text output.
# encodedimbno is rendered via TrueType barcode overlay at its own position,
# never as plain text in the address block.
_ALWAYS_SKIP: frozenset[str] = frozenset({"encodedimbno"})

# Legacy top→bottom field ordering applied when template is empty/None.
# Mirrors the default field list in apps/mailmerge/services.py (_DEFAULT_FIELDS)
# reversed from bottom→top to top→bottom printing order, excluding barcode-only fields.
# Ordering (top → bottom):
#   imbno, name, company, urbanization, sec-primary street, primary street, city-state-zip
_LEGACY_FIELDS_TOP_TO_BOTTOM: list[str] = [
    "imbno",
    "name",
    "company",
    "urbanization",
    "sec-primary street",
    "primary street",
    "city-state-zip",
]


@dataclass
class TemplateLine:
    """A single parsed line from an imposition/address template.

    kind:
        - ``"static"``  — pure text with no ``{token}`` markers.
        - ``"field"``   — a single ``{field}`` token (field name lowercased).
        - ``"br"``      — ``{br}`` or ``{blank}`` — force an empty line.
        - ``"mixed"``   — text with one or more ``{token}`` markers interleaved.
    raw:
        The original template line string.
    field:
        Lowercased field name for ``kind="field"`` lines; ``None`` otherwise.
    tokens:
        List of token names (as they appear in the template, not lowercased)
        for ``kind="mixed"`` lines; empty otherwise.
    """

    kind: Literal["static", "field", "br", "mixed"]
    raw: str
    field: str | None = None
    tokens: list[str] = _field(default_factory=list)


def parse_imposition_template(template: str) -> list[TemplateLine]:
    """Tokenize *template* string into a list of :class:`TemplateLine` objects.

    Returns an empty list when *template* is falsy or contains only whitespace;
    :func:`render_imposition_lines` will apply the legacy fallback in that case.
    """
    if not template or not template.strip():
        return []

    result: list[TemplateLine] = []
    for raw_line in template.splitlines():
        tokens = _TOKEN_RE.findall(raw_line)

        if not tokens:
            # Pure static text — include non-blank lines only.
            if raw_line.strip():
                result.append(TemplateLine(kind="static", raw=raw_line))
            # Blank/whitespace-only lines without tokens are silently dropped;
            # use {br} or {blank} to force an explicit blank slot.
            continue

        if len(tokens) == 1 and raw_line.strip() == "{" + tokens[0] + "}":
            field = tokens[0].lower()
            if field in ("br", "blank"):
                result.append(TemplateLine(kind="br", raw=raw_line, field=field))
            else:
                result.append(TemplateLine(kind="field", raw=raw_line, field=field))
            continue

        # Mixed line: text with one or more tokens interleaved.
        result.append(TemplateLine(kind="mixed", raw=raw_line, tokens=tokens))

    return result


def render_imposition_lines(
    record: dict[str, str],
    template_ast: list[TemplateLine],
    *,
    skip_fields: frozenset[str] | None = None,
) -> list[str]:
    """Apply *record* values to *template_ast* and return rendered lines.

    Lines are returned in **top → bottom** printing order.

    Parameters
    ----------
    record:
        Mapping of CSV field names (lowercased) to their values.
    template_ast:
        Parsed template returned by :func:`parse_imposition_template`.
        When the list is empty the legacy fallback field ordering is used
        (see :data:`_LEGACY_FIELDS_TOP_TO_BOTTOM`).
    skip_fields:
        Additional field names (lowercased) to suppress from the rendered
        output beyond the always-filtered set (``encodedimbno``).
        Used by callers that render certain fields at a separate position
        (e.g. ``presorttrayid`` when a dedicated tray position is configured).
    """
    effective_skip = _ALWAYS_SKIP | (skip_fields or frozenset())

    if not template_ast:
        # Legacy fallback: deterministic field ordering when no template exists.
        lines: list[str] = []
        for f in _LEGACY_FIELDS_TOP_TO_BOTTOM:
            if f in effective_skip:
                continue
            val = (record.get(f, "") or "").strip()
            if val:
                lines.append(val)
        return lines

    rendered: list[str] = []
    for line in template_ast:
        if line.kind == "static":
            rendered.append(line.raw)
        elif line.kind == "br":
            rendered.append("")
        elif line.kind == "field":
            assert line.field is not None  # always set for kind="field"
            if line.field in effective_skip:
                continue
            val = (record.get(line.field, "") or "").strip()
            if not val:
                continue
            rendered.append(val)
        elif line.kind == "mixed":
            substituted = _TOKEN_RE.sub(
                lambda m: record.get(m.group(1), "")
                or record.get(m.group(1).lower(), ""),
                line.raw,
            ).strip()
            if substituted:
                rendered.append(substituted)

    return rendered
