/**
 * mailmerge/detail.js
 * Alpine.js component for the mail merge job detail / record preview page.
 * Exports: window.mmDetail (called via x-data in the template)
 * Requires: pdfjsLib on window (load pdf.min.js before this script)
 * Requires: window.PDFJS_WORKER_SRC set by the template inline config script
 * Requires: window.MAILMERGE_IMB_FONT_URL set by the template inline config script
 * Requires: window._DETAIL_CFG set by the template inline config script
 * Requires: Alpine.js loaded after this script
 */

// Configure pdfjs worker if the URL was set by the template.
(function () {
  if (typeof pdfjsLib !== 'undefined' && window.PDFJS_WORKER_SRC) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = window.PDFJS_WORKER_SRC;
  }
})();

var PT_PER_IN_D = 72;

function mmDetail(artworkUrl, recordsUrl) {
  return {
    records: [],
    recordIdx: 0,
    canvasReady: false,
    _pdfDoc: null,
    _bgCanvas: null,
    _bgValid: false,
    _scale: 1,
    _imbFont: null,

    get currentRecord() {
      return this.records[this.recordIdx] || null;
    },

    get currentRecordLines() {
      var rec = this.currentRecord;
      if (!rec) return [];
      var fields = (_DETAIL_CFG.csvFields && _DETAIL_CFG.csvFields.length)
        ? _DETAIL_CFG.csvFields
        : ['encodedimbno', 'city-state-zip', 'primary street', 'sec-primary street', 'urbanization', 'company', 'name', 'presorttrayid'];
      var out = [];
      // Reverse to show top-to-bottom on screen
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

    _resolvePositions() {
      var cardWPt = _DETAIL_CFG.cardWPt || 432;
      var cardHPt = _DETAIL_CFG.cardHPt || 288;
      var addrX = cardWPt - (_DETAIL_CFG.addrXIn != null ? _DETAIL_CFG.addrXIn : 4.5) * PT_PER_IN_D;
      var addrY = (_DETAIL_CFG.addrYIn != null ? _DETAIL_CFG.addrYIn : 2.5) * PT_PER_IN_D;
      var barcodeX = _DETAIL_CFG.barcodeXIn != null ? (cardWPt - _DETAIL_CFG.barcodeXIn * PT_PER_IN_D) : addrX;
      var barcodeY = _DETAIL_CFG.barcodeYIn != null ? _DETAIL_CFG.barcodeYIn * PT_PER_IN_D : addrY;
      var trayX = _DETAIL_CFG.trayXIn != null ? (cardWPt - _DETAIL_CFG.trayXIn * PT_PER_IN_D) : addrX;
      var trayY = _DETAIL_CFG.trayYIn != null ? _DETAIL_CFG.trayYIn * PT_PER_IN_D : null;
      return { cardWPt: cardWPt, cardHPt: cardHPt, addrX: addrX, addrY: addrY,
               barcodeX: barcodeX, barcodeY: barcodeY, trayX: trayX, trayY: trayY };
    },

    _drawAddressText(ctx, pos, scale) {
      var rec = this.currentRecord;
      if (!rec) return;
      var fields = (_DETAIL_CFG.csvFields && _DETAIL_CFG.csvFields.length)
        ? _DETAIL_CFG.csvFields
        : ['encodedimbno', 'city-state-zip', 'primary street', 'sec-primary street', 'urbanization', 'company', 'name', 'presorttrayid'];
      var fontSizePt   = _DETAIL_CFG.fontPt        != null ? _DETAIL_CFG.fontPt        : 9;
      var lineHeightPt = _DETAIL_CFG.lineHeightPt  != null ? _DETAIL_CFG.lineHeightPt  : 13;
      var barcodeFontPt = _DETAIL_CFG.barcodeFontPt != null ? _DETAIL_CFG.barcodeFontPt : 14;
      var trayFontPt   = _DETAIL_CFG.trayFontPt    != null ? _DETAIL_CFG.trayFontPt    : fontSizePt;
      var hasSeparateTray = pos.trayY != null;

      var lines = [];
      for (var i = 0; i < fields.length; i++) {
        var f = fields[i];
        var val = (rec[f] || '').trim();
        if (!val) continue;
        if (f === 'encodedimbno') continue;
        if (f === 'presorttrayid' && hasSeparateTray) continue;
        lines.push(val);
      }

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

    _cacheBg(canvas) {
      if (!this._bgCanvas) this._bgCanvas = document.createElement('canvas');
      this._bgCanvas.width = canvas.width;
      this._bgCanvas.height = canvas.height;
      this._bgCanvas.getContext('2d').drawImage(canvas, 0, 0);
      this._bgValid = true;
    },

    _renderCanvas() {
      var canvas = document.getElementById('detailPreviewCanvas');
      if (!canvas) return;
      var pos = this._resolvePositions();
      var container = canvas.closest('.card-body') || canvas.parentElement;
      var maxW = (container.clientWidth || 600) - 24;
      var maxH = 300;
      var scale = Math.min(maxW / pos.cardWPt, maxH / pos.cardHPt, 1);
      this._scale = scale;
      var ctx = canvas.getContext('2d');
      var self = this;

      var renderPage = function(doc) {
        var pageIdx = Math.max(0, _DETAIL_CFG.mergePageIdx || 0);
        doc.getPage(pageIdx + 1).then(function(page) {
          var viewport = page.getViewport({ scale: scale });
          canvas.width  = viewport.width;
          canvas.height = viewport.height;
          page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function() {
            self._cacheBg(canvas);
            self.canvasReady = true;
            self._drawAddressText(ctx, pos, scale);
          });
        }).catch(function() { self.canvasReady = false; });
      };

      if (this._pdfDoc) {
        renderPage(this._pdfDoc);
      } else if (typeof pdfjsLib !== 'undefined') {
        // Fetch artwork with credentials so authenticated sessions work,
        // then pass ArrayBuffer to PDF.js to avoid cross-origin/cookie issues.
        fetch(artworkUrl, { credentials: 'same-origin' })
          .then(function(r) { if (!r.ok) throw new Error('Fetch failed'); return r.arrayBuffer(); })
          .then(function(buf) {
            var typedarray = new Uint8Array(buf);
            return pdfjsLib.getDocument({ data: typedarray }).promise;
          })
          .then(function(doc) {
            self._pdfDoc = doc;
            renderPage(doc);
          })
          .catch(function() { self.canvasReady = false; });
      }
    },

    _drawOverlay() {
      var canvas = document.getElementById('detailPreviewCanvas');
      if (!canvas || !this.canvasReady) return;
      var ctx = canvas.getContext('2d');
      if (this._bgValid && this._bgCanvas) {
        ctx.drawImage(this._bgCanvas, 0, 0);
      } else {
        this._renderCanvas();
        return;
      }
      var pos = this._resolvePositions();
      this._drawAddressText(ctx, pos, this._scale);
    },

    onKeyNav(e) {
      if (this.records.length < 2) return;
      if (e.key === 'ArrowLeft') this.prevRecord();
      if (e.key === 'ArrowRight') this.nextRecord();
    },

    init() {
      var self = this;

      // Load IMb font
      if (typeof FontFace !== 'undefined' && window.MAILMERGE_IMB_FONT_URL) {
        var face = new FontFace('USPSIMBStandard', 'url(' + window.MAILMERGE_IMB_FONT_URL + ')');
        face.load().then(function(loaded) {
          document.fonts.add(loaded);
          self._imbFont = loaded;
          if (self.canvasReady) self._drawOverlay();
        }).catch(function() {});
      }

      // Fetch records from server. Accept either {records: [...]} or a raw array.
      fetch(recordsUrl, { credentials: 'same-origin' })
        .then(function(r) {
          if (!r.ok) throw new Error('records fetch failed');
          return r.json();
        })
        .then(function(data) {
          // Support both { records: [...] } and direct array responses
          var list = [];
          if (Array.isArray(data)) list = data;
          else if (Array.isArray(data.records)) list = data.records;
          self.records = list || [];
          if (self.records.length) {
            if (typeof self.$nextTick === 'function') {
              self.$nextTick(function() { self._renderCanvas(); });
            } else {
              setTimeout(function() { self._renderCanvas(); }, 0);
            }
          }
        })
        .catch(function(err) { console.debug('mailmerge: records fetch error', err); });
    },
  };
}
