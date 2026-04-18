/**
 * mailmerge/preview.js
 * Single source of truth for all mailmerge canvas preview rendering.
 * Requires: pdfjsLib on window (load pdf.min.js before this script)
 * Requires: window.imposeTemplate from impose/template.js (load before this script)
 * Requires: Alpine.js loaded after this script
 * Exports: window.mailMergeUpload, window.mailMergeEdit
 *
 * DO NOT duplicate preview logic in templates — all changes go here.
 * DO NOT duplicate template parsing — use imposeTemplate.buildLinesFromTemplate().
 *
 * Shared helpers (module-level, used by both factories):
 *   _resolveAllPositions(cfg, cardWPt, cardHPt) → position object
 *   _drawRecordOverlay(ctx, pos, scale, rec, cfg, imbFont) → canonical rendering
 */

if (typeof pdfjsLib === 'undefined') {
  console.error('preview.js: pdfjsLib not loaded — include pdf.min.js before this script');
}

// Configure pdfjs worker if the URL was set by the template.
(function () {
  if (typeof pdfjsLib !== 'undefined' && window.PDFJS_WORKER_SRC) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = window.PDFJS_WORKER_SRC;
  }
})();

var PT_PER_IN = 72;
var LINE_HEIGHT = 13;

// Default CSV field order used when cfg.csvFields is empty.
// Bottom-to-top display order; matches the DEFAULT_CSV_FIELDS list in models.py.
var _DEFAULT_CSV_FIELDS = [
  'encodedimbno',     // rendered as USPS IMb visual barcode
  'city-state-zip',
  'primary street',
  'sec-primary street',
  'urbanization',
  'company',
  'name',
  'presorttrayid'
];

/* ── CSV helpers ─────────────────────────────────────────────────────────── */

function _parseSimpleCsv(text) {
  var lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  if (lines.length < 2) return [];
  var headers = _csvSplitLine(lines[0]).map(function (h) { return h.trim().toLowerCase(); });
  var records = [];
  for (var i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    var vals = _csvSplitLine(lines[i]);
    var rec = {};
    headers.forEach(function (h, idx) { rec[h] = (vals[idx] || '').trim(); });
    records.push(rec);
  }
  return records;
}

function _csvSplitLine(line) {
  var result = [], current = '', inQuote = false;
  for (var i = 0; i < line.length; i++) {
    var c = line[i];
    if (c === '"') {
      if (inQuote && line[i + 1] === '"') { current += '"'; i++; }
      else inQuote = !inQuote;
    } else if (c === ',' && !inQuote) {
      result.push(current); current = '';
    } else {
      current += c;
    }
  }
  result.push(current);
  return result;
}

/* ── Shared preview helpers (used by all preview surfaces) ──────────────── */

/**
 * Resolve all drawing positions from a config object and card dimensions.
 * x-position config values are "from the right edge" (inches); converted here
 * to PDF left-edge points.
 *
 * @param {Object} cfg   - addrXIn, addrYIn, barcodeXIn, barcodeYIn, trayXIn, trayYIn
 * @param {number} cardWPt  - card width in points
 * @param {number} cardHPt  - card height in points
 * @returns {{ cardWPt, cardHPt, addrX, addrY, barcodeX, barcodeY, trayX, trayY }}
 */
function _resolveAllPositions(cfg, cardWPt, cardHPt) {
  var addrX = cardWPt - (cfg.addrXIn != null ? cfg.addrXIn : 4.5) * PT_PER_IN;
  var addrY = (cfg.addrYIn != null ? cfg.addrYIn : 2.5) * PT_PER_IN;
  var barcodeX = cfg.barcodeXIn != null ? (cardWPt - cfg.barcodeXIn * PT_PER_IN) : addrX;
  var barcodeY = cfg.barcodeYIn != null ? cfg.barcodeYIn * PT_PER_IN : addrY;
  var trayX = cfg.trayXIn != null ? (cardWPt - cfg.trayXIn * PT_PER_IN) : addrX;
  var trayY = cfg.trayYIn != null ? cfg.trayYIn * PT_PER_IN : null;
  return {
    cardWPt: cardWPt, cardHPt: cardHPt,
    addrX: addrX, addrY: addrY,
    barcodeX: barcodeX, barcodeY: barcodeY,
    trayX: trayX, trayY: trayY
  };
}

/**
 * Draw the address block (text + barcode + tray) for a single record on canvas.
 * This is the single authoritative rendering path for all preview surfaces —
 * matches the server-side rendering in services.py / _address_text_stream().
 * Requires imposeTemplate.buildLinesFromTemplate() (impose/template.js).
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {{ addrX, addrY, barcodeX, barcodeY, trayX, trayY, cardHPt }} pos
 * @param {number} scale   - canvas-to-points scale factor
 * @param {Object|null} rec  - CSV record (keys lowercased); no-op when null
 * @param {Object} cfg     - fontPt, lineHeightPt, barcodeFontPt, trayFontPt, addressTemplate
 * @param {FontFace|null} imbFont  - loaded USPSIMBStandard font, or null
 */
function _drawRecordOverlay(ctx, pos, scale, rec, cfg, imbFont) {
  if (!rec) return;
  var fontSizePt = cfg.fontPt != null ? cfg.fontPt : 9;
  var lineHeightPt = cfg.lineHeightPt != null ? cfg.lineHeightPt : 13;
  var barcodeFontPt = cfg.barcodeFontPt != null ? cfg.barcodeFontPt : 14;
  var trayFontPt = cfg.trayFontPt != null ? cfg.trayFontPt : fontSizePt;
  var hasSeparateTray = pos.trayY != null;

  // Build address lines using the canonical template builder (top → bottom).
  // Reverse to bottom → top for y-offset drawing (lines[0] drawn at baseY).
  var lines = imposeTemplate.buildLinesFromTemplate(
    rec, cfg.addressTemplate || '', { skipTray: hasSeparateTray }
  ).slice().reverse();

  if (lines.length) {
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.85)';
    ctx.font = Math.max(6, fontSizePt * scale) + 'px Helvetica, Arial, sans-serif';
    ctx.textAlign = 'left';
    var lineH = lineHeightPt * scale;
    var baseY = (pos.cardHPt - pos.addrY) * scale;
    for (var j = 0; j < lines.length; j++) {
      ctx.fillText(lines[j], pos.addrX * scale, baseY - j * lineH);
    }
    ctx.restore();
  }

  // Draw USPS IMb barcode (encodedimbno)
  var barcodeVal = (rec['encodedimbno'] || '').trim();
  if (barcodeVal) {
    ctx.save();
    var bFontPx = Math.max(8, barcodeFontPt * scale);
    if (imbFont) {
      ctx.font = bFontPx + 'px USPSIMBStandard';
    } else {
      ctx.font = 'italic ' + Math.max(6, 8 * scale) + 'px monospace';
      barcodeVal = '[Barcode] ' + barcodeVal.substring(0, 20);
    }
    ctx.fillStyle = 'rgba(0,0,0,0.85)';
    ctx.textAlign = 'left';
    ctx.fillText(barcodeVal, pos.barcodeX * scale, (pos.cardHPt - pos.barcodeY) * scale);
    ctx.restore();
  }

  // Draw tray ID (presorttrayid) at its dedicated position
  if (hasSeparateTray) {
    var trayVal = (rec['presorttrayid'] || '').trim();
    if (trayVal) {
      ctx.save();
      ctx.font = Math.max(6, trayFontPt * scale) + 'px Helvetica, Arial, sans-serif';
      ctx.fillStyle = 'rgba(0,0,0,0.85)';
      ctx.textAlign = 'left';
      ctx.fillText(trayVal, pos.trayX * scale, (pos.cardHPt - pos.trayY) * scale);
      ctx.restore();
    }
  }
}

/* ── Admin: AddressBlockConfig canvas drawing ────────────────────────────── */

(function () {
  'use strict';

  var PT = 72;          // points per inch
  var SNAP = 72 / 16;   // snap = 0.0625" in points

  var DEFAULT_TEMPLATE = [
    '{presorttrayid}',
    '{name}',
    '{company}',
    '{urbanization}',
    '{sec-primary street}',
    '{primary street}',
    '{city-state-zip}',
    '{encodedimbno}'
  ].join('\n');

  /* ── Form input helpers ──────────────────────────────────────────────── */
  function fv(id, def) {
    var el = document.getElementById(id);
    if (!el || el.value.trim() === '') return def;
    var v = parseFloat(el.value);
    return isNaN(v) ? def : v;
  }
  function sv(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : '';
  }
  function setInput(id, val) {
    var el = document.getElementById(id);
    if (el) {
      el.value = val;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }
  function fmt(pt) {
    return (pt / PT).toFixed(4).replace(/\.?0+$/, '');
  }
  function snapVal(pt, lo, hi) {
    return Math.round(Math.max(lo, Math.min(pt, hi)) / SNAP) * SNAP;
  }

  /* ── Derived state (recomputed each frame) ───────────────────────────── */
  var S = {
    cardWPt: 0, cardHPt: 0,
    addrXPt: 0, addrYPt: 0,
    barXPt: 0, barYPt: 0, barFsPt: 0,
    trayXPt: 0, trayYPt: 0, trayFsPt: 0, hasTray: false,
    fsPt: 0, lhPt: 0, addrBlockWPt: 0, addrBlockHPt: 0,
    tmpl: '',
    scale: 1,
    dragging: null, dragOX: 0, dragOY: 0
  };

  function readState() {
    var cardW = fv('id_preview_card_width_in', 6);
    var cardH = fv('id_preview_card_height_in', 9);
    S.cardWPt = cardW * PT;
    S.cardHPt = cardH * PT;

    var addrXR = sv('id_addr_x_in');
    var addrY = sv('id_addr_y_in');
    S.addrXPt = S.cardWPt - (addrXR !== '' ? parseFloat(addrXR) : 4.5) * PT;
    S.addrYPt = addrY !== '' ? parseFloat(addrY) * PT : 2.5 * PT;

    var barXR = sv('id_barcode_x_in');
    var barY = sv('id_barcode_y_in');
    S.barXPt = barXR !== '' ? S.cardWPt - parseFloat(barXR) * PT : S.addrXPt;
    S.barYPt = barY !== '' ? parseFloat(barY) * PT : S.addrYPt;
    S.barFsPt = fv('id_barcode_font_size', 14);

    var trayXR = sv('id_tray_x_in');
    var trayY = sv('id_tray_y_in');
    S.hasTray = trayXR !== '' && trayY !== '';
    S.trayXPt = S.hasTray ? S.cardWPt - parseFloat(trayXR) * PT : 0;
    S.trayYPt = S.hasTray ? parseFloat(trayY) * PT : 0;
    S.trayFsPt = fv('id_tray_font_size', fv('id_font_size', 9));

    S.fsPt = fv('id_font_size', 9);
    S.lhPt = fv('id_line_height', 13);
    S.addrBlockWPt = fv('id_addr_block_width_in', 4.25) * PT;

    S.tmpl = sv('id_address_template') || DEFAULT_TEMPLATE;
    var visLines = S.tmpl.split('\n').filter(function (l) {
      var t = l.trim();
      return t && t !== '{encodedimbno}';
    });
    S.addrBlockHPt = Math.max(1, visLines.length) * S.lhPt;
  }

  /* ── Canvas drawing ──────────────────────────────────────────────────── */
  function redraw() {
    var canvas = document.getElementById('mm-preview-canvas');
    if (!canvas) return;
    readState();
    var wrap = canvas.parentElement;
    var maxW = (wrap ? wrap.clientWidth - 16 : 300);
    var maxH = 340;
    var scale = Math.min(maxW / S.cardWPt, maxH / S.cardHPt, 1);
    canvas.width = Math.round(S.cardWPt * scale);
    canvas.height = Math.round(S.cardHPt * scale);
    S.scale = scale;
    var ctx = canvas.getContext('2d');
    drawAll(ctx, canvas.width, canvas.height, scale);
    updateLabel();
  }

  function drawAll(ctx, w, h, scale) {
    ctx.fillStyle = '#f8fafc';
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#cbd5e1';
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, w - 1, h - 1);

    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 0.5;
    for (var gx = PT; gx < S.cardWPt; gx += PT) {
      var cx = gx * scale;
      ctx.beginPath(); ctx.moveTo(cx, 0); ctx.lineTo(cx, h); ctx.stroke();
    }
    for (var gy = PT; gy < S.cardHPt; gy += PT) {
      var cy = gy * scale;
      ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(w, cy); ctx.stroke();
    }

    ctx.fillStyle = '#94a3b8';
    ctx.font = Math.max(9, 11 * scale) + 'px sans-serif';
    ctx.textAlign = 'center';
    var cardWIn = (S.cardWPt / PT).toFixed(2).replace(/\.?0+$/, '');
    var cardHIn = (S.cardHPt / PT).toFixed(2).replace(/\.?0+$/, '');
    ctx.fillText(cardWIn + '\u2033 \u00d7 ' + cardHIn + '\u2033', w / 2, h / 2);

    drawAddressBlock(ctx, scale);
    drawBarcodeIndicator(ctx, scale);
    if (S.hasTray) drawTrayIndicator(ctx, scale);
  }

  function drawAddressBlock(ctx, scale) {
    var cx = S.addrXPt * scale;
    var cy = (S.cardHPt - S.addrYPt - S.addrBlockHPt) * scale;
    var cw = S.addrBlockWPt * scale;
    var ch = S.addrBlockHPt * scale;

    ctx.save();
    ctx.fillStyle = 'rgba(59,130,246,0.12)';
    ctx.fillRect(cx, cy, cw, ch);
    ctx.strokeStyle = 'rgba(59,130,246,0.7)';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(cx, cy, cw, ch);

    var lines = S.tmpl.split('\n').filter(function (l) {
      var t = l.trim();
      return t && t !== '{encodedimbno}';
    });
    var fs = Math.max(6, Math.min(S.fsPt, 11) * scale);
    ctx.font = fs + 'px monospace';
    ctx.textAlign = 'left';
    for (var i = 0; i < lines.length; i++) {
      var lineY = cy + (i + 0.8) * S.lhPt * scale;
      var label = lines[i].replace(/\{([^}]+)\}/g, function (_, token) {
        return token.toLowerCase() === 'br' ? '' : token;
      });
      ctx.fillStyle = i === 0 ? 'rgba(59,130,246,0.85)' : 'rgba(59,130,246,0.6)';
      ctx.fillText(label, cx + 3 * scale, lineY);
    }
    ctx.restore();
  }

  function drawBarcodeIndicator(ctx, scale) {
    var barH = S.barFsPt;
    var barW = S.addrBlockWPt;
    var cx = S.barXPt * scale;
    var cy = (S.cardHPt - S.barYPt - barH) * scale;
    var cw = barW * scale;
    var ch = Math.max(3, barH * scale);

    ctx.save();
    ctx.fillStyle = 'rgba(245,158,11,0.13)';
    ctx.fillRect(cx, cy, cw, ch);
    ctx.strokeStyle = 'rgba(245,158,11,0.85)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(cx, cy, cw, ch);
    ctx.setLineDash([]);

    var barCount = 12;
    var barSpacing = cw / (barCount * 2 + 1);
    ctx.strokeStyle = 'rgba(180,110,0,0.55)';
    ctx.lineWidth = Math.max(1, barSpacing * 0.7);
    for (var i = 0; i < barCount; i++) {
      var bxi = cx + barSpacing * (i * 2 + 1);
      var barTop = (i % 3 === 0) ? cy : cy + ch * 0.25;
      var barBot = (i % 3 === 1) ? cy + ch * 0.75 : cy + ch;
      ctx.beginPath(); ctx.moveTo(bxi, barTop); ctx.lineTo(bxi, barBot); ctx.stroke();
    }
    ctx.fillStyle = 'rgba(180,110,0,0.9)';
    ctx.font = 'bold ' + Math.max(7, 8 * scale) + 'px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('IMb', cx + 3 * scale, cy + Math.max(9, barH * scale * 0.75));
    ctx.restore();
  }

  function drawTrayIndicator(ctx, scale) {
    var lineH = S.trayFsPt;
    var approxW = lineH * 4.5;
    var cx = S.trayXPt * scale;
    var cy = (S.cardHPt - S.trayYPt - lineH) * scale;
    var cw = approxW * scale;
    var ch = Math.max(3, lineH * scale);

    ctx.save();
    ctx.fillStyle = 'rgba(34,197,94,0.13)';
    ctx.fillRect(cx, cy, cw, ch);
    ctx.strokeStyle = 'rgba(34,197,94,0.85)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(cx, cy, cw, ch);
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(21,128,61,0.95)';
    ctx.font = Math.max(7, 8 * scale) + 'px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Tray', cx + 2 * scale, cy + Math.max(8, lineH * scale * 0.82));
    ctx.restore();
  }

  function updateLabel() {
    var el = document.getElementById('mm-preview-label');
    if (!el) return;
    var addrXR = (S.cardWPt - S.addrXPt) / PT;
    var addrY = S.addrYPt / PT;
    var barXR = (S.cardWPt - S.barXPt) / PT;
    var barY = S.barYPt / PT;
    var f = function (v) { return v.toFixed(4).replace(/\.?0+$/, ''); };
    var parts = [
      'Addr x:' + f(addrXR) + '\u2033R  y:' + f(addrY) + '\u2033',
      'IMb x:' + f(barXR) + '\u2033R  y:' + f(barY) + '\u2033'
    ];
    if (S.hasTray) {
      parts.push('Tray x:' + f((S.cardWPt - S.trayXPt) / PT) + '\u2033R  y:' + f(S.trayYPt / PT) + '\u2033');
    }
    el.textContent = parts.join('   \u00b7   ');
  }

  /* ── Hit testing ─────────────────────────────────────────────────────── */
  function hitAddr(cx, cy) {
    var sc = S.scale;
    var bx = S.addrXPt * sc;
    var by = (S.cardHPt - S.addrYPt - S.addrBlockHPt) * sc;
    return cx >= bx && cx <= bx + S.addrBlockWPt * sc &&
      cy >= by && cy <= by + S.addrBlockHPt * sc;
  }
  function hitBarcode(cx, cy) {
    var sc = S.scale;
    var barH = S.barFsPt;
    var bx = S.barXPt * sc;
    var by = (S.cardHPt - S.barYPt - barH) * sc;
    return cx >= bx && cx <= bx + S.addrBlockWPt * sc &&
      cy >= by && cy <= by + Math.max(3, barH) * sc;
  }
  function hitTray(cx, cy) {
    if (!S.hasTray) return false;
    var sc = S.scale;
    var lineH = S.trayFsPt;
    var approxW = lineH * 4.5;
    var bx = S.trayXPt * sc;
    var by = (S.cardHPt - S.trayYPt - lineH) * sc;
    return cx >= bx && cx <= bx + approxW * sc &&
      cy >= by && cy <= by + Math.max(3, lineH) * sc;
  }

  function evCoords(e) {
    var canvas = document.getElementById('mm-preview-canvas');
    var rect = canvas.getBoundingClientRect();
    var scaleX = canvas.width / rect.width;
    var scaleY = canvas.height / rect.height;
    var src = (e.touches && e.touches.length) ? e.touches[0] : e;
    return {
      x: (src.clientX - rect.left) * scaleX,
      y: (src.clientY - rect.top) * scaleY
    };
  }

  /* ── Drag handlers ───────────────────────────────────────────────────── */
  function onMouseDown(e) {
    var c = evCoords(e);
    readState();
    if (hitTray(c.x, c.y)) {
      S.dragging = 'tray';
      S.dragOX = c.x - S.trayXPt * S.scale;
      S.dragOY = c.y - (S.cardHPt - S.trayYPt - S.trayFsPt) * S.scale;
    } else if (hitBarcode(c.x, c.y)) {
      S.dragging = 'barcode';
      S.dragOX = c.x - S.barXPt * S.scale;
      S.dragOY = c.y - (S.cardHPt - S.barYPt - S.barFsPt) * S.scale;
    } else if (hitAddr(c.x, c.y)) {
      S.dragging = 'addr';
      S.dragOX = c.x - S.addrXPt * S.scale;
      S.dragOY = c.y - (S.cardHPt - S.addrYPt - S.addrBlockHPt) * S.scale;
    }
    if (S.dragging) {
      e.target.style.cursor = 'grabbing';
      e.preventDefault();
    }
  }

  function onMouseMove(e) {
    if (!S.dragging) return;
    e.preventDefault();
    var c = evCoords(e);
    var sc = S.scale;
    var newL = (c.x - S.dragOX) / sc;
    var newTop = (c.y - S.dragOY) / sc;

    if (S.dragging === 'addr') {
      var ay = S.cardHPt - newTop - S.addrBlockHPt;
      var sx = snapVal(newL, 0, S.cardWPt - S.addrBlockWPt);
      var sy = snapVal(ay, 0, S.cardHPt - S.addrBlockHPt);
      S.addrXPt = sx; S.addrYPt = sy;
      setInput('id_addr_x_in', fmt(S.cardWPt - sx));
      setInput('id_addr_y_in', fmt(sy));

    } else if (S.dragging === 'barcode') {
      var by2 = S.cardHPt - newTop - S.barFsPt;
      var sx2 = snapVal(newL, 0, S.cardWPt - S.addrBlockWPt);
      var sy2 = snapVal(by2, 0, S.cardHPt - S.barFsPt);
      S.barXPt = sx2; S.barYPt = sy2;
      setInput('id_barcode_x_in', fmt(S.cardWPt - sx2));
      setInput('id_barcode_y_in', fmt(sy2));

    } else if (S.dragging === 'tray') {
      var lineH = S.trayFsPt;
      var approxW = lineH * 4.5;
      var ty2 = S.cardHPt - newTop - lineH;
      var sx3 = snapVal(newL, 0, S.cardWPt - approxW);
      var sy3 = snapVal(ty2, 0, S.cardHPt - lineH);
      S.trayXPt = sx3; S.trayYPt = sy3;
      setInput('id_tray_x_in', fmt(S.cardWPt - sx3));
      setInput('id_tray_y_in', fmt(sy3));
    }
    redraw();
  }

  function onMouseUp() {
    if (S.dragging) {
      S.dragging = null;
      var canvas = document.getElementById('mm-preview-canvas');
      if (canvas) canvas.style.cursor = 'grab';
    }
  }

  /* ── Bootstrap ───────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    var canvas = document.getElementById('mm-preview-canvas');
    if (!canvas) return;

    // If the address_template field is blank, pre-fill it with the default
    // so the canvas and the actual PDF generation are in sync. Without this,
    // an empty DB field makes the canvas show a preview but the service uses
    // the legacy field-list path instead, and tokens like {ase} silently do nothing.
    var ta = document.getElementById('id_address_template');
    if (ta && ta.value.trim() === '') {
      ta.value = DEFAULT_TEMPLATE;
    }

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('mouseleave', onMouseUp);
    canvas.addEventListener('touchstart', function (e) { e.preventDefault(); onMouseDown(e); }, { passive: false });
    canvas.addEventListener('touchmove', function (e) { e.preventDefault(); onMouseMove(e); }, { passive: false });
    canvas.addEventListener('touchend', function (e) { e.preventDefault(); onMouseUp(); }, { passive: false });

    var watchIds = [
      'id_preview_card_width_in', 'id_preview_card_height_in',
      'id_addr_x_in', 'id_addr_y_in',
      'id_barcode_x_in', 'id_barcode_y_in', 'id_barcode_font_size',
      'id_tray_x_in', 'id_tray_y_in', 'id_tray_font_size',
      'id_font_size', 'id_line_height', 'id_addr_block_width_in',
      'id_address_template'
    ];
    watchIds.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('input', redraw);
      if (el) el.addEventListener('change', redraw);
    });

    redraw();
  });
})();

/* ── Alpine factory: upload page ─────────────────────────────────────────── */

window.mailMergeUpload = function mailMergeUpload(cfg) {
  return {
    pdfInfo: null,
    mergePage: 1,
    uploadingArtwork: false,
    _artworkFile: null,
    _pdfDoc: null,
    _scale: 1,
    _cardWPt: 0,
    _cardHPt: 0,
    _bgCanvas: null,
    _bgValid: false,
    _imbFont: null,
    records: [],
    recordIdx: 0,
    csvTab: 'upload',
    nm: { month: '', year: '', loading: false, error: '', success: '', downloadUrl: null, downloadFilename: '' },
    pco: { lists: [], listId: '', loading: false, listsLoading: false, listsLoaded: false, error: '', success: '', downloadUrl: null, downloadFilename: '' },

    get currentRecord() {
      return this.records[this.recordIdx] || null;
    },

    prevRecord() {
      if (this.recordIdx > 0) { this.recordIdx--; this._drawOverlay(); }
    },
    nextRecord() {
      if (this.recordIdx < this.records.length - 1) { this.recordIdx++; this._drawOverlay(); }
    },

    _getCardInfo() {
      if (!this.pdfInfo || !this.pdfInfo.pages) return null;
      var idx = Math.max(0, this.mergePage - 1);
      return this.pdfInfo.pages[idx] || null;
    },

    // Resolve all drawing positions from config + page dimensions.
    _resolvePositions(pageInfo) {
      return _resolveAllPositions(cfg, pageInfo.width_pt, pageInfo.height_pt);
    },

    onMergePageChange(page) {
      this.mergePage = page;
      this._pdfDoc = null;
      this._bgValid = false;
      this.renderPreview();
    },

    onArtworkChange(event) {
      var file = event.target.files[0];
      if (!file) { this.pdfInfo = null; return; }
      this._artworkFile = file;
      this._pdfDoc = null;
      this._bgValid = false;
      this.uploadingArtwork = true;

      var self = this;
      var formData = new FormData();
      formData.append('artwork_file', file);
      formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

      var inspectUrl = window.MAILMERGE_INSPECT_URL || cfg.inspectUrl || '';
      fetch(inspectUrl, {
        method: 'POST',
        body: formData,
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          self.pdfInfo = data;
          self.mergePage = 1;
          self.uploadingArtwork = false;
          self.$nextTick(function () { self.renderPreview(); });
        })
        .catch(function () { self.pdfInfo = null; self.uploadingArtwork = false; });
    },

    onCsvChange(event) {
      var file = event.target.files[0];
      if (!file) { this.records = []; return; }
      var self = this;
      var reader = new FileReader();
      reader.onload = function (e) {
        var text = e.target.result;
        self.records = _parseSimpleCsv(text);
        self.recordIdx = 0;
        self._drawOverlay();
      };
      reader.readAsText(file);
    },

    switchCsvTab(tab) {
      if (this.csvTab === 'newmovers' && tab !== 'newmovers') {
        if (this.nm.downloadUrl) { URL.revokeObjectURL(this.nm.downloadUrl); }
        this.nm.downloadUrl = null; this.nm.downloadFilename = ''; this.nm.success = '';
      }
      if (this.csvTab === 'pco' && tab !== 'pco') {
        if (this.pco.downloadUrl) { URL.revokeObjectURL(this.pco.downloadUrl); }
        this.pco.downloadUrl = null; this.pco.downloadFilename = ''; this.pco.success = '';
      }
      this.csvTab = tab;
      if (tab === 'pco') this.loadPcoLists();
    },

    async pullNewMovers() {
      this.nm.error = '';
      this.nm.success = '';
      if (!this.nm.month || !this.nm.year) { this.nm.error = 'Please enter a month and year.'; return; }
      if (this.nm.downloadUrl) { URL.revokeObjectURL(this.nm.downloadUrl); this.nm.downloadUrl = null; this.nm.downloadFilename = ''; }
      this.nm.loading = true;
      try {
        const url = '/mailmerge/new-movers-csv/?month=' + this.nm.month + '&year=' + this.nm.year;
        const res = await fetch(url);
        if (!res.ok) { const d = await res.json(); this.nm.error = d.error || 'Request failed.'; return; }
        const blob = await res.blob();
        const cd = res.headers.get('Content-Disposition') || '';
        const nameMatch = cd.match(/filename=\"?([^\"]+)\"?/);
        const filename = nameMatch ? nameMatch[1] : 'new_movers.csv';
        const file = new File([blob], filename, { type: 'text/csv' });
        const dt = new DataTransfer();
        dt.items.add(file);
        const input = document.getElementById('csv_file');
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        this.nm.downloadUrl = URL.createObjectURL(blob);
        this.nm.downloadFilename = filename;
        this.nm.success = filename + ' loaded (' + file.size.toLocaleString() + ' bytes)';
      } catch (e) {
        this.nm.error = 'Network error: ' + e.message;
      } finally {
        this.nm.loading = false;
      }
    },

    async loadPcoLists() {
      if (this.pco.listsLoading) return;
      this.pco.listsLoading = true;
      this.pco.error = '';
      try {
        const res = await fetch('/mailmerge/pco-lists/');
        const data = await res.json();
        if (!res.ok) { this.pco.error = data.error || 'Failed to load lists.'; return; }
        this.pco.lists = data.lists || [];
        this.pco.listsLoaded = true;
      } catch (e) {
        this.pco.error = 'Network error: ' + e.message;
      } finally {
        this.pco.listsLoading = false;
      }
    },

    async pullPcoList() {
      if (!this.pco.listId) return;
      this.pco.error = '';
      this.pco.success = '';
      // Revoke previous download to free memory
      if (this.pco.downloadUrl) { URL.revokeObjectURL(this.pco.downloadUrl); this.pco.downloadUrl = null; this.pco.downloadFilename = ''; }
      this.pco.loading = true;
      try {
        const url = '/mailmerge/pco-csv/?list_id=' + encodeURIComponent(this.pco.listId);
        const res = await fetch(url);
        if (!res.ok) { const d = await res.json(); this.pco.error = d.error || 'Request failed.'; return; }
        const blob = await res.blob();
        const cd = res.headers.get('Content-Disposition') || '';
        const nameMatch = cd.match(/filename="?([^"]+)"?/);
        const filename = nameMatch ? nameMatch[1] : 'pco_list.csv';
        const file = new File([blob], filename, { type: 'text/csv' });
        const dt = new DataTransfer();
        dt.items.add(file);
        const input = document.getElementById('csv_file');
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        this.pco.downloadUrl = URL.createObjectURL(blob);
        this.pco.downloadFilename = filename;
        this.pco.success = filename + ' loaded (' + file.size.toLocaleString() + ' bytes)';
      } catch (e) {
        this.pco.error = 'Network error: ' + e.message;
      } finally {
        this.pco.loading = false;
      }
    },

    renderPreview() {
      var canvas = document.getElementById('previewCanvas');
      if (!canvas || !this.pdfInfo || !this.pdfInfo.pages) return;

      var pageInfo = this._getCardInfo();
      if (!pageInfo) return;

      var pos = this._resolvePositions(pageInfo);
      var maxW = canvas.parentElement.clientWidth - 24;
      var maxH = 300;
      var scale = Math.min(maxW / pos.cardWPt, maxH / pos.cardHPt, 1);
      canvas.width = Math.round(pos.cardWPt * scale);
      canvas.height = Math.round(pos.cardHPt * scale);

      this._scale = scale;
      this._cardWPt = pos.cardWPt;
      this._cardHPt = pos.cardHPt;
      this._bgValid = false;

      var ctx = canvas.getContext('2d');
      var self = this;

      if (this._artworkFile && typeof pdfjsLib !== 'undefined') {
        var pageIdx = Math.max(0, this.mergePage - 1);

        var renderPage = function (doc) {
          doc.getPage(pageIdx + 1).then(function (page) {
            var viewport = page.getViewport({ scale: scale });
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function () {
              self._cacheBg(canvas);
              self._drawAddressText(ctx, pos, scale);
            });
          }).catch(function () {
            self._drawPlaceholder(ctx, canvas.width, canvas.height, pos, scale);
          });
        };

        if (this._pdfDoc) {
          renderPage(this._pdfDoc);
        } else {
          var reader = new FileReader();
          reader.onload = function (e) {
            var typedarray = new Uint8Array(e.target.result);
            pdfjsLib.getDocument({ data: typedarray }).promise.then(function (doc) {
              self._pdfDoc = doc;
              renderPage(doc);
            }).catch(function () {
              self._drawPlaceholder(ctx, canvas.width, canvas.height, pos, scale);
            });
          };
          reader.readAsArrayBuffer(self._artworkFile);
        }
      } else {
        this._drawPlaceholder(ctx, canvas.width, canvas.height, pos, scale);
      }
    },

    _cacheBg(canvas) {
      if (!this._bgCanvas) this._bgCanvas = document.createElement('canvas');
      this._bgCanvas.width = canvas.width;
      this._bgCanvas.height = canvas.height;
      this._bgCanvas.getContext('2d').drawImage(canvas, 0, 0);
      this._bgValid = true;
    },

    _drawOverlay() {
      var canvas = document.getElementById('previewCanvas');
      if (!canvas) return;
      var pageInfo = this._getCardInfo();
      if (!pageInfo) return;
      var pos = this._resolvePositions(pageInfo);
      var scale = this._scale || 1;
      var ctx = canvas.getContext('2d');
      if (this._bgValid && this._bgCanvas) {
        ctx.drawImage(this._bgCanvas, 0, 0);
      } else {
        this.renderPreview();
        return;
      }
      this._drawAddressText(ctx, pos, scale);
    },

    _drawPlaceholder(ctx, w, h, pos, scale) {
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 1;
      ctx.strokeRect(0.5, 0.5, w - 1, h - 1);
      ctx.fillStyle = '#94a3b8';
      ctx.font = Math.max(10, 14 * scale) + 'px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Artwork page ' + this.mergePage, w / 2, h / 2 - 8 * scale);
      ctx.font = Math.max(8, 11 * scale) + 'px sans-serif';
      ctx.fillText('(upload a PDF to see preview)', w / 2, h / 2 + 8 * scale);
      this._bgValid = false;
      this._drawAddressText(ctx, pos, scale);
    },

    _drawAddressText(ctx, pos, scale) {
      _drawRecordOverlay(ctx, pos, scale, this.currentRecord, cfg, this._imbFont);
    },

    onKeyNav(e) {
      if (this.records.length < 2) return;
      if (e.key === 'ArrowLeft') this.prevRecord();
      if (e.key === 'ArrowRight') this.nextRecord();
    },

    init() {
      if (typeof FontFace !== 'undefined') {
        var self = this;
        var fontUrl = window.MAILMERGE_IMB_FONT_URL || '';
        if (fontUrl) {
          var face = new FontFace('USPSIMBStandard', 'url(' + fontUrl + ')');
          face.load().then(function (loaded) {
            document.fonts.add(loaded);
            self._imbFont = loaded;
          }).catch(function () { });
        }
      }
    },
  };
};

/* ── Alpine factory: edit/detail page ───────────────────────────────────── */

/**
 * Alpine data factory for edit and detail pages.
 * Loads artwork from server URL, fetches records, and renders the canonical
 * address+barcode+tray overlay using _drawRecordOverlay().
 *
 * cfg properties:
 *   artworkUrl      {string}        URL to serve the artwork PDF (required)
 *   recordsUrl      {string}        URL returning { records: [...] } JSON
 *   cardWPt         {number}        card width in points (from job.card_width)
 *   cardHPt         {number}        card height in points (from job.card_height)
 *   mergePageIdx    {number}        0-based page index that receives the address
 *   pageCount       {number}        total artwork page count
 *   addrXIn         {number|null}   address block left edge, inches from right
 *   addrYIn         {number|null}   address block bottom, inches from bottom
 *   fontPt          {number|null}   address text font size in points
 *   lineHeightPt    {number|null}   address line height in points
 *   barcodeFontPt   {number|null}   IMb barcode font size in points
 *   barcodeXIn      {number|null}   barcode left edge, inches from right
 *   barcodeYIn      {number|null}   barcode baseline, inches from bottom
 *   trayXIn         {number|null}   tray ID left edge, inches from right
 *   trayYIn         {number|null}   tray ID baseline, inches from bottom
 *   trayFontPt      {number|null}   tray ID font size in points
 *   addressTemplate {string}        address template string
 *   csvFields       {string[]}      ordered CSV field names (for text fallback)
 *   canvasId        {string}        canvas element id (default: 'previewCanvas')
 */
window.mailMergeEdit = function mailMergeEdit(cfg) {
  return {
    cardWPt: cfg.cardWPt || 432,
    cardHPt: cfg.cardHPt || 288,
    mergePage: (cfg.mergePageIdx || 0) + 1,
    pageCount: cfg.pageCount || 1,
    _pdfDoc: null,
    _scale: 1,
    _bgCanvas: null,
    _bgValid: false,
    _imbFont: null,
    canvasReady: false,
    pdfInfo: null,
    records: [],
    recordIdx: 0,

    get currentRecord() {
      return this.records[this.recordIdx] || null;
    },

    // Returns field-value pairs for the text fallback display.
    get currentRecordLines() {
      var rec = this.currentRecord;
      if (!rec) return [];
      var fields = (cfg.csvFields && cfg.csvFields.length) ? cfg.csvFields : _DEFAULT_CSV_FIELDS;
      var out = [];
      for (var i = fields.length - 1; i >= 0; i--) {
        var val = (rec[fields[i]] || '').trim();
        if (val) out.push({ field: fields[i], value: val });
      }
      return out;
    },

    prevRecord() {
      if (this.recordIdx > 0) { this.recordIdx--; this._drawOverlay(); }
    },
    nextRecord() {
      if (this.recordIdx < this.records.length - 1) { this.recordIdx++; this._drawOverlay(); }
    },

    onMergePageChange(page) {
      this.mergePage = page;
      this._pdfDoc = null;
      this._bgValid = false;
      this.renderPreview();
    },

    onKeyNav(e) {
      if (this.records.length < 2) return;
      if (e.key === 'ArrowLeft') this.prevRecord();
      if (e.key === 'ArrowRight') this.nextRecord();
    },

    _getCanvas() {
      return document.getElementById(cfg.canvasId || 'previewCanvas');
    },

    _resolvePos() {
      return _resolveAllPositions(cfg, this.cardWPt, this.cardHPt);
    },

    renderPreview() {
      var canvas = this._getCanvas();
      if (!canvas) return;
      var pos = this._resolvePos();
      var maxW = (canvas.parentElement ? canvas.parentElement.clientWidth : 600) - 24;
      var maxH = 300;
      var scale = Math.min(maxW / pos.cardWPt, maxH / pos.cardHPt, 1);
      canvas.width = Math.round(pos.cardWPt * scale);
      canvas.height = Math.round(pos.cardHPt * scale);
      this._scale = scale;
      this._bgValid = false;

      var ctx = canvas.getContext('2d');
      var self = this;
      var pageIdx = Math.max(0, this.mergePage - 1);

      if (cfg.artworkUrl && typeof pdfjsLib !== 'undefined') {
        var renderPage = function (doc) {
          doc.getPage(pageIdx + 1).then(function (page) {
            var viewport = page.getViewport({ scale: scale });
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function () {
              self._cacheBg(canvas);
              self.canvasReady = true;
              _drawRecordOverlay(ctx, self._resolvePos(), self._scale, self.currentRecord, cfg, self._imbFont);
            });
          }).catch(function () { self.canvasReady = false; });
        };

        if (this._pdfDoc) {
          renderPage(this._pdfDoc);
        } else {
          // Fetch with credentials so authenticated Django sessions work correctly.
          fetch(cfg.artworkUrl, { credentials: 'same-origin' })
            .then(function (r) { if (!r.ok) throw new Error('Artwork fetch failed: HTTP ' + r.status); return r.arrayBuffer(); })
            .then(function (buf) { return pdfjsLib.getDocument({ data: new Uint8Array(buf) }).promise; })
            .then(function (doc) {
              self._pdfDoc = doc;
              renderPage(doc);
            })
            .catch(function () { self.canvasReady = false; });
        }
      } else {
        this._drawPlaceholder(ctx, canvas.width, canvas.height);
      }
    },

    _cacheBg(canvas) {
      if (!this._bgCanvas) this._bgCanvas = document.createElement('canvas');
      this._bgCanvas.width = canvas.width;
      this._bgCanvas.height = canvas.height;
      this._bgCanvas.getContext('2d').drawImage(canvas, 0, 0);
      this._bgValid = true;
    },

    _drawOverlay() {
      var canvas = this._getCanvas();
      if (!canvas || !this.canvasReady) return;
      var ctx = canvas.getContext('2d');
      if (this._bgValid && this._bgCanvas) {
        ctx.drawImage(this._bgCanvas, 0, 0);
      } else {
        this.renderPreview();
        return;
      }
      _drawRecordOverlay(ctx, this._resolvePos(), this._scale, this.currentRecord, cfg, this._imbFont);
    },

    _drawPlaceholder(ctx, w, h) {
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 1;
      ctx.strokeRect(0.5, 0.5, w - 1, h - 1);
      ctx.fillStyle = '#94a3b8';
      ctx.font = Math.max(10, 14 * this._scale) + 'px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Page ' + this.mergePage, w / 2, h / 2);
      this.canvasReady = false;
    },

    init() {
      var self = this;

      // Load IMb font
      if (typeof FontFace !== 'undefined') {
        var fontUrl = window.MAILMERGE_IMB_FONT_URL || '';
        if (fontUrl) {
          var face = new FontFace('USPSIMBStandard', 'url(' + fontUrl + ')');
          face.load().then(function (loaded) {
            document.fonts.add(loaded);
            self._imbFont = loaded;
            if (self.canvasReady) self._drawOverlay();
          }).catch(function () { });
        }
      }

      // Load records from server if URL provided; then render preview.
      if (cfg.recordsUrl) {
        fetch(cfg.recordsUrl, { credentials: 'same-origin' })
          .then(function (r) { if (!r.ok) throw new Error('records fetch failed'); return r.json(); })
          .then(function (data) {
            var list = Array.isArray(data) ? data : (Array.isArray(data.records) ? data.records : []);
            self.records = list;
            if (typeof self.$nextTick === 'function') {
              self.$nextTick(function () { self.renderPreview(); });
            } else {
              setTimeout(function () { self.renderPreview(); }, 0);
            }
          })
          .catch(function (err) { console.debug('mailmerge: records fetch error', err); });
      } else {
        // No records URL — render artwork only.
        if (typeof self.$nextTick === 'function') {
          self.$nextTick(function () { self.renderPreview(); });
        } else {
          setTimeout(function () { self.renderPreview(); }, 0);
        }
      }
    },
  };
};
