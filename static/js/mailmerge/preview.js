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

/* ── CSV helpers ─────────────────────────────────────────────────────────── */

function _parseSimpleCsv(text) {
  var lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  if (lines.length < 2) return [];
  var headers = _csvSplitLine(lines[0]).map(function(h) { return h.trim().toLowerCase(); });
  var records = [];
  for (var i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    var vals = _csvSplitLine(lines[i]);
    var rec = {};
    headers.forEach(function(h, idx) { rec[h] = (vals[idx] || '').trim(); });
    records.push(rec);
  }
  return records;
}

function _csvSplitLine(line) {
  var result = [], current = '', inQuote = false;
  for (var i = 0; i < line.length; i++) {
    var c = line[i];
    if (c === '"') {
      if (inQuote && line[i+1] === '"') { current += '"'; i++; }
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
    var addrY  = sv('id_addr_y_in');
    S.addrXPt = S.cardWPt - (addrXR !== '' ? parseFloat(addrXR) : 4.5) * PT;
    S.addrYPt = addrY !== '' ? parseFloat(addrY) * PT : 2.5 * PT;

    var barXR = sv('id_barcode_x_in');
    var barY  = sv('id_barcode_y_in');
    S.barXPt = barXR !== '' ? S.cardWPt - parseFloat(barXR) * PT : S.addrXPt;
    S.barYPt = barY  !== '' ? parseFloat(barY) * PT : S.addrYPt;
    S.barFsPt = fv('id_barcode_font_size', 14);

    var trayXR = sv('id_tray_x_in');
    var trayY  = sv('id_tray_y_in');
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
    var maxW  = (wrap ? wrap.clientWidth - 16 : 300);
    var maxH  = 340;
    var scale = Math.min(maxW / S.cardWPt, maxH / S.cardHPt, 1);
    canvas.width  = Math.round(S.cardWPt * scale);
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
    var cx   = S.barXPt * scale;
    var cy   = (S.cardHPt - S.barYPt - barH) * scale;
    var cw   = barW * scale;
    var ch   = Math.max(3, barH * scale);

    ctx.save();
    ctx.fillStyle   = 'rgba(245,158,11,0.13)';
    ctx.fillRect(cx, cy, cw, ch);
    ctx.strokeStyle = 'rgba(245,158,11,0.85)';
    ctx.lineWidth   = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(cx, cy, cw, ch);
    ctx.setLineDash([]);

    var barCount   = 12;
    var barSpacing = cw / (barCount * 2 + 1);
    ctx.strokeStyle = 'rgba(180,110,0,0.55)';
    ctx.lineWidth   = Math.max(1, barSpacing * 0.7);
    for (var i = 0; i < barCount; i++) {
      var bxi    = cx + barSpacing * (i * 2 + 1);
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
    var lineH  = S.trayFsPt;
    var approxW = lineH * 4.5;
    var cx = S.trayXPt * scale;
    var cy = (S.cardHPt - S.trayYPt - lineH) * scale;
    var cw = approxW * scale;
    var ch = Math.max(3, lineH * scale);

    ctx.save();
    ctx.fillStyle   = 'rgba(34,197,94,0.13)';
    ctx.fillRect(cx, cy, cw, ch);
    ctx.strokeStyle = 'rgba(34,197,94,0.85)';
    ctx.lineWidth   = 1.5;
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
    var addrY  = S.addrYPt / PT;
    var barXR  = (S.cardWPt - S.barXPt) / PT;
    var barY   = S.barYPt / PT;
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
    var lineH  = S.trayFsPt;
    var approxW = lineH * 4.5;
    var bx = S.trayXPt * sc;
    var by = (S.cardHPt - S.trayYPt - lineH) * sc;
    return cx >= bx && cx <= bx + approxW * sc &&
           cy >= by && cy <= by + Math.max(3, lineH) * sc;
  }

  function evCoords(e) {
    var canvas = document.getElementById('mm-preview-canvas');
    var rect   = canvas.getBoundingClientRect();
    var scaleX = canvas.width / rect.width;
    var scaleY = canvas.height / rect.height;
    var src    = (e.touches && e.touches.length) ? e.touches[0] : e;
    return {
      x: (src.clientX - rect.left) * scaleX,
      y: (src.clientY - rect.top)  * scaleY
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
    var c  = evCoords(e);
    var sc = S.scale;
    var newL   = (c.x - S.dragOX) / sc;
    var newTop = (c.y - S.dragOY) / sc;

    if (S.dragging === 'addr') {
      var ay  = S.cardHPt - newTop - S.addrBlockHPt;
      var sx  = snapVal(newL, 0, S.cardWPt - S.addrBlockWPt);
      var sy  = snapVal(ay,   0, S.cardHPt - S.addrBlockHPt);
      S.addrXPt = sx; S.addrYPt = sy;
      setInput('id_addr_x_in', fmt(S.cardWPt - sx));
      setInput('id_addr_y_in', fmt(sy));

    } else if (S.dragging === 'barcode') {
      var by2 = S.cardHPt - newTop - S.barFsPt;
      var sx2 = snapVal(newL, 0, S.cardWPt - S.addrBlockWPt);
      var sy2 = snapVal(by2,  0, S.cardHPt - S.barFsPt);
      S.barXPt = sx2; S.barYPt = sy2;
      setInput('id_barcode_x_in', fmt(S.cardWPt - sx2));
      setInput('id_barcode_y_in', fmt(sy2));

    } else if (S.dragging === 'tray') {
      var lineH  = S.trayFsPt;
      var approxW = lineH * 4.5;
      var ty2 = S.cardHPt - newTop - lineH;
      var sx3 = snapVal(newL, 0, S.cardWPt - approxW);
      var sy3 = snapVal(ty2,  0, S.cardHPt - lineH);
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

    canvas.addEventListener('mousedown',  onMouseDown);
    canvas.addEventListener('mousemove',  onMouseMove);
    canvas.addEventListener('mouseup',    onMouseUp);
    canvas.addEventListener('mouseleave', onMouseUp);
    canvas.addEventListener('touchstart', function (e) { e.preventDefault(); onMouseDown(e); }, { passive: false });
    canvas.addEventListener('touchmove',  function (e) { e.preventDefault(); onMouseMove(e); }, { passive: false });
    canvas.addEventListener('touchend',   function (e) { e.preventDefault(); onMouseUp();    }, { passive: false });

    var watchIds = [
      'id_preview_card_width_in', 'id_preview_card_height_in',
      'id_addr_x_in',    'id_addr_y_in',
      'id_barcode_x_in', 'id_barcode_y_in', 'id_barcode_font_size',
      'id_tray_x_in',    'id_tray_y_in',    'id_tray_font_size',
      'id_font_size',    'id_line_height',   'id_addr_block_width_in',
      'id_address_template'
    ];
    watchIds.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('input',  redraw);
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
    _artworkFile: null,
    _pdfDoc: null,
    _scale: 1,
    _cardWPt: 0,
    _cardHPt: 0,
    _bgCanvas: null,
    _bgValid: false,
    _imbFont: null,
    csvRecords: [],
    recordIdx: 0,

    get currentRecord() {
      return this.csvRecords[this.recordIdx] || null;
    },

    prevRecord() {
      if (this.recordIdx > 0) { this.recordIdx--; this._drawOverlay(); }
    },
    nextRecord() {
      if (this.recordIdx < this.csvRecords.length - 1) { this.recordIdx++; this._drawOverlay(); }
    },

    _getCardInfo() {
      if (!this.pdfInfo || !this.pdfInfo.pages) return null;
      var idx = Math.max(0, this.mergePage - 1);
      return this.pdfInfo.pages[idx] || null;
    },

    // Resolve all drawing positions from config + page dimensions.
    // x values in config are from-right; convert to PDF left-edge points.
    _resolvePositions(pageInfo) {
      var cardWPt = pageInfo.width_pt;
      var cardHPt = pageInfo.height_pt;
      var addrX = cardWPt - (cfg.addrXIn != null ? cfg.addrXIn : 4.5) * PT_PER_IN;
      var addrY = (cfg.addrYIn != null ? cfg.addrYIn : 2.5) * PT_PER_IN;
      var barcodeX = cfg.barcodeXIn != null ? (cardWPt - cfg.barcodeXIn * PT_PER_IN) : addrX;
      var barcodeY = cfg.barcodeYIn != null ? cfg.barcodeYIn * PT_PER_IN : addrY;
      var trayX = cfg.trayXIn != null ? (cardWPt - cfg.trayXIn * PT_PER_IN) : addrX;
      var trayY = cfg.trayYIn != null ? cfg.trayYIn * PT_PER_IN : null;
      return { cardWPt: cardWPt, cardHPt: cardHPt, addrX: addrX, addrY: addrY,
               barcodeX: barcodeX, barcodeY: barcodeY, trayX: trayX, trayY: trayY };
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

      var self = this;
      var formData = new FormData();
      formData.append('artwork_file', file);
      formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

      var inspectUrl = window.MAILMERGE_INSPECT_URL || cfg.inspectUrl || '';
      fetch(inspectUrl, {
        method: 'POST',
        body: formData,
      })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          self.pdfInfo = data;
          self.mergePage = 1;
          self.$nextTick(function() { self.renderPreview(); });
        })
        .catch(function() { self.pdfInfo = null; });
    },

    onCsvChange(event) {
      var file = event.target.files[0];
      if (!file) { this.csvRecords = []; return; }
      var self = this;
      var reader = new FileReader();
      reader.onload = function(e) {
        var text = e.target.result;
        self.csvRecords = _parseSimpleCsv(text);
        self.recordIdx = 0;
        self._drawOverlay();
      };
      reader.readAsText(file);
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
      canvas.width  = Math.round(pos.cardWPt * scale);
      canvas.height = Math.round(pos.cardHPt * scale);

      this._scale = scale;
      this._cardWPt = pos.cardWPt;
      this._cardHPt = pos.cardHPt;
      this._bgValid = false;

      var ctx = canvas.getContext('2d');
      var self = this;

      if (this._artworkFile && typeof pdfjsLib !== 'undefined') {
        var pageIdx = Math.max(0, this.mergePage - 1);

        var renderPage = function(doc) {
          doc.getPage(pageIdx + 1).then(function(page) {
            var viewport = page.getViewport({ scale: scale });
            canvas.width  = viewport.width;
            canvas.height = viewport.height;
            page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function() {
              self._cacheBg(canvas);
              self._drawAddressText(ctx, pos, scale);
            });
          }).catch(function() {
            self._drawPlaceholder(ctx, canvas.width, canvas.height, pos, scale);
          });
        };

        if (this._pdfDoc) {
          renderPage(this._pdfDoc);
        } else {
          var reader = new FileReader();
          reader.onload = function(e) {
            var typedarray = new Uint8Array(e.target.result);
            pdfjsLib.getDocument({ data: typedarray }).promise.then(function(doc) {
              self._pdfDoc = doc;
              renderPage(doc);
            }).catch(function() {
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
      var rec = this.currentRecord;
      if (!rec) return;

      var fontSizePt   = cfg.fontPt        != null ? cfg.fontPt        : 9;
      var lineHeightPt = cfg.lineHeightPt  != null ? cfg.lineHeightPt  : 13;
      var barcodeFontPt = cfg.barcodeFontPt != null ? cfg.barcodeFontPt : 14;
      var trayFontPt   = cfg.trayFontPt    != null ? cfg.trayFontPt    : fontSizePt;
      var hasSeparateTray = pos.trayY != null;

      // Build address lines using the canonical template builder (top → bottom).
      // Reverse to bottom → top for y-offset drawing (lines[0] drawn at baseY).
      var lines = imposeTemplate.buildLinesFromTemplate(
        rec, cfg.addressTemplate || '', { skipTray: hasSeparateTray }
      ).slice().reverse();

      // Draw regular address text
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
        if (this._imbFont) {
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
    },

    onKeyNav(e) {
      if (this.csvRecords.length < 2) return;
      if (e.key === 'ArrowLeft') this.prevRecord();
      if (e.key === 'ArrowRight') this.nextRecord();
    },

    init() {
      if (typeof FontFace !== 'undefined') {
        var self = this;
        var fontUrl = window.MAILMERGE_IMB_FONT_URL || '';
        if (fontUrl) {
          var face = new FontFace('USPSIMBStandard', 'url(' + fontUrl + ')');
          face.load().then(function(loaded) {
            document.fonts.add(loaded);
            self._imbFont = loaded;
          }).catch(function() {});
        }
      }
    },
  };
};

/* ── Alpine factory: edit/detail page ───────────────────────────────────── */

window.mailMergeEdit = function mailMergeEdit(cardWPt, cardHPt, pageCount, initialMergePage, artworkUrl, recordsUrl, cfgAddrXIn, cfgAddrYIn, cfgAddrBlockWidthIn, cfgNumFields, cfgAddrTemplate) {
  var addrBlockWPt = (cfgAddrBlockWidthIn || 4.25) * PT_PER_IN;
  var numLines     = cfgNumFields || 7;
  var addrBlockHPt = numLines * LINE_HEIGHT;

  return {
    cardWPt: cardWPt || 432,
    cardHPt: cardHPt || 288,
      addrTemplate: cfgAddrTemplate || '',
    pageCount: pageCount || 1,
    mergePage: initialMergePage || 1,
    _pdfDoc: null,
    _scale: 1,
    artworkUrl: artworkUrl,
    recordsUrl: recordsUrl,
    // Cached background canvas
    _bgCanvas: null,
    _bgValid: false,
    // Record preview
    records: [],
    recordIdx: 0,

    get currentRecord() {
      return this.records[this.recordIdx] || null;
    },

    prevRecord() {
      if (this.recordIdx > 0) { this.recordIdx--; this._drawOverlay(); }
    },
    nextRecord() {
      if (this.recordIdx < this.records.length - 1) { this.recordIdx++; this._drawOverlay(); }
    },

    _resolveAddrPt() {
      // cfgAddrXIn is inches from the RIGHT edge; convert to PDF left-edge points
      var addrX = this.cardWPt - (cfgAddrXIn != null ? cfgAddrXIn : 4.5) * PT_PER_IN;
      var addrY = (cfgAddrYIn != null ? cfgAddrYIn : 2.5) * PT_PER_IN;
      return { addrX: addrX, addrY: addrY };
    },

    init() {
      var self = this;
      this.$nextTick(function() { self.renderPreview(); });
      // Load existing records
      if (this.recordsUrl) {
        fetch(this.recordsUrl)
          .then(function(r) { return r.json(); })
          .then(function(data) { self.records = data.records || []; })
          .catch(function() {});
      }
    },

    onKeyNav(e) {
      if (this.records.length < 2) return;
      if (e.key === 'ArrowLeft') this.prevRecord();
      if (e.key === 'ArrowRight') this.nextRecord();
    },

    onMergePageChange(page) {
      this.mergePage = page;
      this._pdfDoc = null;
      this._bgValid = false;
      this.renderPreview();
    },

    renderPreview() {
      var canvas = document.getElementById('previewCanvas');
      if (!canvas) return;

      var cardWPt = this.cardWPt;
      var cardHPt = this.cardHPt;
      var p = this._resolveAddrPt();
      var addrX = p.addrX, addrY = p.addrY;

      var maxW = canvas.parentElement.clientWidth - 24;
      var maxH = 300;
      var scale = Math.min(maxW / cardWPt, maxH / cardHPt, 1);
      canvas.width  = Math.round(cardWPt * scale);
      canvas.height = Math.round(cardHPt * scale);
      this._scale = scale;
      this._bgValid = false;

      var ctx = canvas.getContext('2d');
      var self = this;
      var pageIdx = Math.max(0, this.mergePage - 1);

      if (this.artworkUrl && typeof pdfjsLib !== 'undefined') {
        var renderPage = function(doc) {
          doc.getPage(pageIdx + 1).then(function(page) {
            var viewport = page.getViewport({ scale: scale });
            canvas.width  = viewport.width;
            canvas.height = viewport.height;
            page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function() {
              self._cacheBg(canvas);
              self._drawAddressBlock(ctx, addrX, addrY, scale, cardHPt);
            });
          }).catch(function() {
            self._drawPlaceholder(ctx, canvas.width, canvas.height, addrX, addrY, scale, cardHPt);
          });
        };

        if (this._pdfDoc) {
          renderPage(this._pdfDoc);
        } else {
          pdfjsLib.getDocument(this.artworkUrl).promise.then(function(doc) {
            self._pdfDoc = doc;
            renderPage(doc);
          }).catch(function() {
            self._drawPlaceholder(ctx, canvas.width, canvas.height, addrX, addrY, scale, cardHPt);
          });
        }
      } else {
        this._drawPlaceholder(ctx, canvas.width, canvas.height, addrX, addrY, scale, cardHPt);
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
      var p = this._resolveAddrPt();
      var scale = this._scale || 1;
      var ctx = canvas.getContext('2d');
      if (this._bgValid && this._bgCanvas) {
        ctx.drawImage(this._bgCanvas, 0, 0);
      } else {
        this.renderPreview();
        return;
      }
      this._drawAddressBlock(ctx, p.addrX, p.addrY, scale, this.cardHPt);
    },

    _drawPlaceholder(ctx, w, h, addrX, addrY, scale, cardHPt) {
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 1;
      ctx.strokeRect(0.5, 0.5, w - 1, h - 1);
      ctx.fillStyle = '#94a3b8';
      ctx.font = Math.max(10, 14 * scale) + 'px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Page ' + this.mergePage, w / 2, h / 2);
      this._drawAddressBlock(ctx, addrX, addrY, scale, cardHPt);
    },

    _drawAddressBlock(ctx, addrX, addrY, scale, cardHPt) {
      var cx = addrX * scale;
      var cy = (cardHPt - addrY - addrBlockHPt) * scale;
      var cw = addrBlockWPt * scale;
      var ch = addrBlockHPt * scale;

      ctx.save();
      ctx.fillStyle = 'rgba(59,130,246,0.12)';
      ctx.fillRect(cx, cy, cw, ch);
      ctx.strokeStyle = 'rgba(59,130,246,0.7)';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(cx, cy, cw, ch);

      var rec = this.currentRecord;
      if (rec) {
        ctx.fillStyle = 'rgba(30,58,138,0.85)';
        var fontSize = Math.max(6, 9 * scale);
        ctx.font = fontSize + 'px monospace';
        ctx.textAlign = 'left';
        var lineH = LINE_HEIGHT * scale;
        // buildLinesFromTemplate returns top→bottom; reverse to bottom→top for drawing.
        var lines = imposeTemplate.buildLinesFromTemplate(rec, this.addrTemplate || '', { skipTray: true }).slice().reverse();
        for (var i = 0; i < lines.length; i++) {
          ctx.fillText(lines[i], cx + 3 * scale, cy + ch - (lines.length - i) * lineH + (lineH - fontSize));
        }
      } else {
        ctx.fillStyle = 'rgba(59,130,246,0.85)';
        ctx.font = 'bold ' + Math.max(8, 9 * scale) + 'px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('Address Block', cx + 3 * scale, cy + 12 * scale);
      }
      ctx.restore();
    },

  };
};
