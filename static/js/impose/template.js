/**
 * impose/template.js
 * Canonical client-side imposition template parser and line builder.
 * All preview surfaces must call imposeTemplate.buildLinesFromTemplate() —
 * do not parse templates inline in templates or other scripts.
 *
 * Token semantics must remain in sync with apps/impose/utils.py.
 * Does not depend on pdfjsLib — compose with preview.js for canvas rendering.
 */

(function (root) {
  'use strict';

  /**
   * Non-address special tokens always filtered from the text flow.
   * encodedimbno is rendered via TrueType barcode overlay, never as plain text.
   */
  var ALWAYS_SKIP = { encodedimbno: true };

  /**
   * Legacy top→bottom field ordering applied when template is empty/null.
   * Mirrors _LEGACY_FIELDS_TOP_TO_BOTTOM in apps/impose/utils.py.
   * Ordering (top → bottom):
   *   imbno, name, company, urbanization, sec-primary street, primary street,
   *   city-state-zip
   */
  var LEGACY_FIELDS_TOP_TO_BOTTOM = [
    'imbno',
    'name',
    'company',
    'urbanization',
    'sec-primary street',
    'primary street',
    'city-state-zip'
  ];

  var TOKEN_RE = /\{([^}]+)\}/g;

  /**
   * _parseTemplate(template)
   *
   * Internal tokenizer — mirrors parse_imposition_template() in utils.py.
   *
   * Returns an array of line objects:
   *   { kind: 'static', raw: '...' }
   *   { kind: 'field',  raw: '...', field: 'lowercased-field-name' }
   *   { kind: 'br',     raw: '...', field: 'br'|'blank' }
   *   { kind: 'mixed',  raw: '...', tokens: ['token1', 'token2'] }
   *
   * Returns [] when template is falsy or whitespace-only.
   */
  function _parseTemplate(template) {
    if (!template || !template.trim()) return [];

    var rawLines = template.split('\n');
    var result = [];

    for (var i = 0; i < rawLines.length; i++) {
      var raw = rawLines[i];
      var tokens = [];
      var m;
      TOKEN_RE.lastIndex = 0;
      while ((m = TOKEN_RE.exec(raw)) !== null) tokens.push(m[1]);

      if (tokens.length === 0) {
        // Pure static text — include non-blank lines only.
        if (raw.trim()) {
          result.push({ kind: 'static', raw: raw });
        }
        // Blank/whitespace-only lines without tokens are silently dropped.
        continue;
      }

      if (tokens.length === 1 && raw.trim() === '{' + tokens[0] + '}') {
        var field = tokens[0].toLowerCase();
        if (field === 'br' || field === 'blank') {
          result.push({ kind: 'br', raw: raw, field: field });
        } else {
          result.push({ kind: 'field', raw: raw, field: field });
        }
        continue;
      }

      // Mixed line: text with one or more tokens interleaved.
      result.push({ kind: 'mixed', raw: raw, tokens: tokens });
    }

    return result;
  }

  /**
   * buildLinesFromTemplate(record, template, options)
   *
   * Apply *record* field values to *template* and return rendered lines in
   * **top → bottom** printing order.  Mirrors render_imposition_lines() in
   * apps/impose/utils.py.
   *
   * Parameters
   * ----------
   * record   {Object}  CSV record — keys lowercased.
   * template {string}  Address template string, or '' / null for legacy mode.
   * options  {Object}  Optional configuration:
   *   skipTray {boolean} When true, suppress {presorttrayid} from the text
   *                      flow (used when tray ID is rendered at a separate
   *                      canvas position).  Default: false.
   *
   * Returns
   * -------
   * {string[]}  Lines in top → bottom order.  Empty strings represent blank
   *             slots produced by {br} or {blank} tokens.
   */
  function buildLinesFromTemplate(record, template, options) {
    var skipTray = options && options.skipTray;
    var ast = _parseTemplate(template);

    // Build a lowercased-key version of the record once to avoid repeated
    // toLowerCase() calls during token substitution in mixed lines.
    var lcRecord = {};
    for (var k in record) {
      if (Object.prototype.hasOwnProperty.call(record, k)) {
        lcRecord[k.toLowerCase()] = record[k];
      }
    }

    if (ast.length === 0) {
      // Legacy fallback: deterministic field ordering.
      var lines = [];
      for (var fi = 0; fi < LEGACY_FIELDS_TOP_TO_BOTTOM.length; fi++) {
        var f = LEGACY_FIELDS_TOP_TO_BOTTOM[fi];
        if (ALWAYS_SKIP[f]) continue;
        if (skipTray && f === 'presorttrayid') continue;
        var v = ((lcRecord[f] || '') + '').trim();
        if (v) lines.push(v);
      }
      return lines;
    }

    var rendered = [];
    for (var i = 0; i < ast.length; i++) {
      var line = ast[i];

      if (line.kind === 'static') {
        rendered.push(line.raw);
        continue;
      }

      if (line.kind === 'br') {
        rendered.push('');
        continue;
      }

      if (line.kind === 'field') {
        var fld = line.field; // already lowercased
        if (ALWAYS_SKIP[fld]) continue;
        if (skipTray && fld === 'presorttrayid') continue;
        var val = ((lcRecord[fld] || '') + '').trim();
        if (!val) continue;
        rendered.push(val);
        continue;
      }

      if (line.kind === 'mixed') {
        TOKEN_RE.lastIndex = 0;
        var substituted = line.raw.replace(TOKEN_RE, function (_, t) {
          return (lcRecord[t.toLowerCase()] || '');
        }).trim();
        if (substituted) rendered.push(substituted);
      }
    }

    return rendered;
  }

  // Expose public API
  root.imposeTemplate = {
    buildLinesFromTemplate: buildLinesFromTemplate,
    /** @internal — exposed for testing only */
    _parseTemplate: _parseTemplate
  };

}(typeof window !== 'undefined' ? window : this));
