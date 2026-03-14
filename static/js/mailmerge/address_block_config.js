/**
 * mailmerge/address_block_config.js
 * Alpine.js component for the address block configuration / canvas preview page.
 * Exports: window.addrBlockConfig (called via x-data in the template)
 * Requires: Alpine.js loaded after this script
 */

var PT_PER_IN     = 72;
var GRID_SNAP_IN  = 0.0625;

var ALL_FIELDS = [
  "encodedimbno",
  "city-state-zip",
  "primary street",
  "sec-primary street",
  "urbanization",
  "company",
  "name",
  "presorttrayid",
  "imbno"
];

var DEFAULT_TEMPLATE = [
  "{presorttrayid}",
  "{name}",
  "{company}",
  "{urbanization}",
  "{sec-primary street}",
  "{primary street}",
  "{city-state-zip}",
  "{encodedimbno}"
].join("\n");

function addrBlockConfig(cfg) {
  return {
    cardWIn:          cfg.cardWIn  || 6,
    cardHIn:          cfg.cardHIn  || 9,
    addrXIn:          cfg.addrXIn  !== undefined ? String(cfg.addrXIn) : '',
    addrYIn:          cfg.addrYIn  !== undefined ? String(cfg.addrYIn) : '',
    fontName:         cfg.fontName  || 'Helvetica',
    fontSize:         cfg.fontSize  || 9,
    lineHeight:       cfg.lineHeight || 13,
    barcodeFontSize:  cfg.barcodeFontSize || 14,
    barcodeXIn:       cfg.barcodeXIn !== undefined ? String(cfg.barcodeXIn) : '',
    barcodeYIn:       cfg.barcodeYIn !== undefined ? String(cfg.barcodeYIn) : '',
    trayXIn:          cfg.trayXIn !== undefined ? String(cfg.trayXIn) : '',
    trayYIn:          cfg.trayYIn !== undefined ? String(cfg.trayYIn) : '',
    trayFontSize:     cfg.trayFontSize || 9,
    addrBlockWidthIn: cfg.addrBlockWidthIn || 4.25,
    addressTemplate:  '',   // loaded in init() from json_script tag
    allFields:        ALL_FIELDS,
    _draggingBlock:   null,
    _dragOffsetX:     0,
    _dragOffsetY:     0,
    _scale:           1,

    get cardWPt() { return parseFloat(this.cardWIn) * PT_PER_IN || 432; },
    get cardHPt() { return parseFloat(this.cardHIn) * PT_PER_IN || 648; },

    get addrBlockWPt() { return parseFloat(this.addrBlockWidthIn) * PT_PER_IN || 306; },
    get addrBlockHPt() {
      // Count visible text lines in the template (excluding blank lines and
      // bare {encodedimbno} which renders as a separate barcode overlay).
      var tmpl = this.addressTemplate || DEFAULT_TEMPLATE;
      var count = tmpl.split('\n').filter(function(l) {
        var t = l.trim();
        if (!t) return false;
        if (t === '{encodedimbno}') return false;
        return true;
      }).length;
      return Math.max(1, count) * parseFloat(this.lineHeight || 13);
    },

    _resolveAddrPt() {
      var addrX = this.cardWPt - (this.addrXIn !== '' ? parseFloat(this.addrXIn) : 4.5) * PT_PER_IN;
      var addrY = this.addrYIn !== '' ? parseFloat(this.addrYIn) * PT_PER_IN
                                      : 2.5 * PT_PER_IN;
      return { addrX: addrX, addrY: addrY };
    },

    _resolveBarcodePt() {
      var p = this._resolveAddrPt();
      return {
        bx: this.barcodeXIn !== '' ? this.cardWPt - parseFloat(this.barcodeXIn) * PT_PER_IN : p.addrX,
        by: this.barcodeYIn !== '' ? parseFloat(this.barcodeYIn) * PT_PER_IN : p.addrY,
      };
    },

    _resolveTrayPt() {
      if (this.trayXIn === '' || this.trayYIn === '') return null;
      return {
        tx: this.cardWPt - parseFloat(this.trayXIn) * PT_PER_IN,
        ty: parseFloat(this.trayYIn) * PT_PER_IN,
      };
    },

    positionLabel() {
      var fmt = function(v) { return parseFloat(v).toFixed(4).replace(/\.?0+$/, ''); };
      var addrXR = this.addrXIn  !== '' ? this.addrXIn  : '4.5';
      var addrY  = this.addrYIn  !== '' ? this.addrYIn  : '2.5';
      var bpXR   = this.barcodeXIn !== '' ? this.barcodeXIn : addrXR;
      var bpY    = this.barcodeYIn !== '' ? this.barcodeYIn : addrY;
      var parts = [
        'Addr  x:' + fmt(addrXR) + '\u2033R  y:' + fmt(addrY) + '\u2033',
        'Barcode  x:' + fmt(bpXR) + '\u2033R  y:' + fmt(bpY) + '\u2033',
      ];
      if (this.trayXIn !== '' && this.trayYIn !== '') {
        parts.push('Tray  x:' + fmt(this.trayXIn) + '\u2033R  y:' + fmt(this.trayYIn) + '\u2033');
      }
      return parts.join('   \u00b7   ');
    },

    // ── Template management ───────────────────────────────────────────────
    insertField(field) {
      var ta = document.getElementById('addressTemplateArea');
      if (!ta) { this.addressTemplate += '\n{' + field + '}'; this.redraw(); return; }
      var start = ta.selectionStart;
      var end   = ta.selectionEnd;
      var token = '{' + field + '}';
      this.addressTemplate = ta.value.slice(0, start) + token + ta.value.slice(end);
      this.$nextTick(function() {
        ta.focus();
        ta.selectionStart = ta.selectionEnd = start + token.length;
      });
      this.redraw();
    },

    resetTemplate() {
      this.addressTemplate = DEFAULT_TEMPLATE;
      this.redraw();
    },

    // ── Canvas ────────────────────────────────────────────────────────────
    applyPreset(w, h) {
      this.cardWIn = w;
      this.cardHIn = h;
      this.redraw();
    },

    onCardSizeChange() { this.redraw(); },

    redraw() {
      var canvas = document.getElementById('previewCanvas');
      if (!canvas) return;
      var cardWPt = this.cardWPt;
      var cardHPt = this.cardHPt;
      var maxW = canvas.parentElement.clientWidth - 24;
      var maxH = 340;
      var scale = Math.min(maxW / cardWPt, maxH / cardHPt, 1);
      canvas.width  = Math.round(cardWPt * scale);
      canvas.height = Math.round(cardHPt * scale);
      this._scale = scale;
      var ctx = canvas.getContext('2d');
      this._drawPlaceholder(ctx, canvas.width, canvas.height);
    },

    _drawPlaceholder(ctx, w, h) {
      var p  = this._resolveAddrPt();
      var bp = this._resolveBarcodePt();
      var tp = this._resolveTrayPt();
      var scale = this._scale || 1;

      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 1;
      ctx.strokeRect(0.5, 0.5, w - 1, h - 1);

      ctx.strokeStyle = '#e2e8f0';
      ctx.lineWidth = 0.5;
      for (var gx = PT_PER_IN; gx < this.cardWPt; gx += PT_PER_IN) {
        var cx = gx * scale;
        ctx.beginPath(); ctx.moveTo(cx, 0); ctx.lineTo(cx, h); ctx.stroke();
      }
      for (var gy = PT_PER_IN; gy < this.cardHPt; gy += PT_PER_IN) {
        var cy = gy * scale;
        ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(w, cy); ctx.stroke();
      }

      ctx.fillStyle = '#94a3b8';
      ctx.font = Math.max(9, 11 * scale) + 'px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(
        parseFloat(this.cardWIn).toFixed(2).replace(/\.?0+$/,'') + '\u2033 \u00d7 ' +
        parseFloat(this.cardHIn).toFixed(2).replace(/\.?0+$/,'') + '\u2033',
        w / 2, h / 2
      );

      this._drawAddressBlock(ctx, p.addrX, p.addrY, scale);
      this._drawBarcodeIndicator(ctx, bp.bx, bp.by, scale);
      if (tp) this._drawTrayIndicator(ctx, tp.tx, tp.ty, scale);
    },

    _drawAddressBlock(ctx, addrX, addrY, scale) {
      var addrBlockWPt = this.addrBlockWPt;
      var addrBlockHPt = this.addrBlockHPt;
      var cx = addrX * scale;
      var cy = (this.cardHPt - addrY - addrBlockHPt) * scale;
      var cw = addrBlockWPt * scale;
      var ch = addrBlockHPt * scale;

      ctx.save();
      ctx.fillStyle = 'rgba(59,130,246,0.12)';
      ctx.fillRect(cx, cy, cw, ch);
      ctx.strokeStyle = 'rgba(59,130,246,0.7)';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(cx, cy, cw, ch);

      // Draw preview lines from template
      var tmpl = this.addressTemplate || DEFAULT_TEMPLATE;
      var lines = tmpl.split('\n').filter(function(l) {
        return l.trim() && l.trim() !== '{encodedimbno}';
      });
      var lh = parseFloat(this.lineHeight || 13);
      var fs = Math.max(6, Math.min(parseFloat(this.fontSize || 9), 11) * scale);
      ctx.font = fs + 'px monospace';
      ctx.textAlign = 'left';
      for (var i = 0; i < lines.length; i++) {
        // y slot: top line has highest slot (n-1), renders highest Y in PDF
        // In canvas coords (Y flipped): top line of template → top of block
        var lineY = cy + (i + 0.8) * lh * scale;
        var label = lines[i].replace(/\{([^}]+)\}/g, '$1');
        ctx.fillStyle = i === 0 ? 'rgba(59,130,246,0.85)' : 'rgba(59,130,246,0.6)';
        ctx.fillText(label, cx + 3 * scale, lineY);
      }
      ctx.restore();
    },

    _drawBarcodeIndicator(ctx, bx, by, scale) {
      var barH  = parseFloat(this.barcodeFontSize || 14);
      var barW  = this.addrBlockWPt;
      var cx    = bx * scale;
      var cy    = (this.cardHPt - by - barH) * scale;
      var cw    = barW * scale;
      var ch    = Math.max(3, barH * scale);

      ctx.save();
      ctx.fillStyle   = 'rgba(245,158,11,0.13)';
      ctx.fillRect(cx, cy, cw, ch);
      ctx.strokeStyle = 'rgba(245,158,11,0.85)';
      ctx.lineWidth   = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.strokeRect(cx, cy, cw, ch);
      ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(180,110,0,0.9)';
      ctx.font = 'bold ' + Math.max(7, 8 * scale) + 'px sans-serif';
      ctx.textAlign = 'left';
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
      ctx.fillText('IMb Barcode', cx + 3 * scale, cy + Math.max(9, barH * scale * 0.75));
      ctx.restore();
    },

    _drawTrayIndicator(ctx, tx, ty, scale) {
      var lineH  = parseFloat(this.trayFontSize || this.fontSize || 9);
      var approxW = lineH * 4.5;
      var cx = tx * scale;
      var cy = (this.cardHPt - ty - lineH) * scale;
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
      ctx.fillText('T00001', cx + 2 * scale, cy + Math.max(8, lineH * scale * 0.82));
      ctx.restore();
    },

    _canvasEventCoords(event) {
      var canvas = document.getElementById('previewCanvas');
      var rect = canvas.getBoundingClientRect();
      var scaleX = canvas.width / rect.width;
      var scaleY = canvas.height / rect.height;
      var src = event.touches ? event.touches[0] : event;
      return {
        cx: (src.clientX - rect.left) * scaleX,
        cy: (src.clientY - rect.top) * scaleY,
      };
    },

    _hitTestAddr(cx, cy) {
      var p = this._resolveAddrPt();
      var scale = this._scale || 1;
      var bx = p.addrX * scale;
      var bh = this.addrBlockHPt;
      var by = (this.cardHPt - p.addrY - bh) * scale;
      return cx >= bx && cx <= bx + this.addrBlockWPt * scale &&
             cy >= by && cy <= by + bh * scale;
    },

    _hitTestBarcode(cx, cy) {
      var bp   = this._resolveBarcodePt();
      var barH = parseFloat(this.barcodeFontSize || 14);
      var barW = this.addrBlockWPt;
      var scale = this._scale || 1;
      var bx = bp.bx * scale;
      var by = (this.cardHPt - bp.by - barH) * scale;
      return cx >= bx && cx <= bx + barW * scale &&
             cy >= by && cy <= by + Math.max(3, barH) * scale;
    },

    _hitTestTray(cx, cy) {
      var tp = this._resolveTrayPt();
      if (!tp) return false;
      var lineH  = parseFloat(this.trayFontSize || this.fontSize || 9);
      var approxW = lineH * 4.5;
      var scale = this._scale || 1;
      var bx = tp.tx * scale;
      var by = (this.cardHPt - tp.ty - lineH) * scale;
      return cx >= bx && cx <= bx + approxW * scale &&
             cy >= by && cy <= by + Math.max(3, lineH) * scale;
    },

    onCanvasMouseDown(event) {
      var coords = this._canvasEventCoords(event);
      var cx = coords.cx, cy = coords.cy;
      var scale = this._scale || 1;

      // Tray is smallest — check it first to allow fine control
      if (this._hitTestTray(cx, cy)) {
        var tp = this._resolveTrayPt();
        var lineH = parseFloat(this.trayFontSize || this.fontSize || 9);
        this._draggingBlock = 'tray';
        this._dragOffsetX = cx - tp.tx * scale;
        this._dragOffsetY = cy - (this.cardHPt - tp.ty - lineH) * scale;
      } else if (this._hitTestBarcode(cx, cy)) {
        var bp   = this._resolveBarcodePt();
        var barH = parseFloat(this.barcodeFontSize || 14);
        this._draggingBlock = 'barcode';
        this._dragOffsetX = cx - bp.bx * scale;
        this._dragOffsetY = cy - (this.cardHPt - bp.by - barH) * scale;
      } else if (this._hitTestAddr(cx, cy)) {
        var p  = this._resolveAddrPt();
        var bh = this.addrBlockHPt;
        this._draggingBlock = 'addr';
        this._dragOffsetX = cx - p.addrX * scale;
        this._dragOffsetY = cy - (this.cardHPt - p.addrY - bh) * scale;
      }
      if (this._draggingBlock) event.target.style.cursor = 'grabbing';
    },

    onCanvasMouseMove(event) {
      if (!this._draggingBlock) return;
      var coords = this._canvasEventCoords(event);
      var scale    = this._scale || 1;
      var cardWPt  = this.cardWPt;
      var cardHPt  = this.cardHPt;
      var snapPt   = GRID_SNAP_IN * PT_PER_IN;
      var newLPt   = (coords.cx - this._dragOffsetX) / scale;
      var newTopCv = (coords.cy - this._dragOffsetY) / scale;

      var snap = function(v, lo, hi) {
        return Math.round(Math.max(lo, Math.min(v, hi)) / snapPt) * snapPt;
      };
      var fmt = function(v) { return (v / PT_PER_IN).toFixed(4).replace(/\.?0+$/, ''); };

      // X values are stored as from-right; newLPt is a left-edge in points.
      // from_right_pt = cardWPt - left_edge_pt
      if (this._draggingBlock === 'addr') {
        var bw = this.addrBlockWPt, bh = this.addrBlockHPt;
        var ay = cardHPt - newTopCv - bh;
        this.addrXIn = fmt(cardWPt - snap(newLPt, 0, cardWPt - bw));
        this.addrYIn = fmt(snap(ay, 0, cardHPt - bh));

      } else if (this._draggingBlock === 'barcode') {
        var barH = parseFloat(this.barcodeFontSize || 14);
        var barW = this.addrBlockWPt;
        var by   = cardHPt - newTopCv - barH;
        this.barcodeXIn = fmt(cardWPt - snap(newLPt, 0, cardWPt - barW));
        this.barcodeYIn = fmt(snap(by, 0, cardHPt - barH));

      } else if (this._draggingBlock === 'tray') {
        var lineH   = parseFloat(this.trayFontSize || this.fontSize || 9);
        var approxW = lineH * 4.5;
        var ty = cardHPt - newTopCv - lineH;
        this.trayXIn = fmt(cardWPt - snap(newLPt, 0, cardWPt - approxW));
        this.trayYIn = fmt(snap(ty, 0, cardHPt - lineH));
      }
      this.redraw();
    },

    onCanvasMouseUp(event) {
      if (this._draggingBlock) {
        this._draggingBlock = null;
        var canvas = document.getElementById('previewCanvas');
        if (canvas) canvas.style.cursor = 'grab';
      }
    },

    onTouchStart(event) { this.onCanvasMouseDown(event); },
    onTouchMove(event)  { this.onCanvasMouseMove(event); },

    init() {
      var self = this;
      // Load template from the json_script tag Django emitted
      var el = document.getElementById('_addr_tmpl');
      if (el) {
        try { self.addressTemplate = JSON.parse(el.textContent); } catch(e) {}
      }
      if (!self.addressTemplate) self.addressTemplate = DEFAULT_TEMPLATE;
      this.$nextTick(function() { self.redraw(); });
    },
  };
}
