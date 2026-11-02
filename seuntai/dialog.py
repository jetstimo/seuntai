# -*- coding: utf-8 -*-
"""
Seuntai - dialog satu klik "Consolidate Lines": pilih layer, centang produk/LOB dari nilai yang ADA di data,
lalu Run. Kolom produk dan kolom tanggal pembuatan dikenali otomatis; bila tidak ada kolom tanggal, peringatan
ditampilkan dan garis terpanjang dipakai (hasil ditandai _TANPA_TANGGAL). Proses berjalan di latar (QgsTask) sehingga
QGIS tetap bisa dipakai; hasil Shapefile kabel tunggal dimuat ke peta setelah selesai.

Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-2.0-or-later (see LICENSE).
"""
import os
import re

from qgis.core import (QgsApplication, QgsFeatureRequest, QgsProcessingAlgRunnerTask, QgsProcessingContext,
                       QgsProcessingFeedback, QgsProject, QgsSettings, QgsSingleSymbolRenderer, QgsVectorLayer,
                       QgsWkbTypes)
from qgis.PyQt.QtCore import Qt, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                                 QListWidgetItem, QComboBox, QProgressBar, QPushButton, QVBoxLayout, QGroupBox)

from . import compat as K
from . import deteksi as D
from . import styles
from . import _log

ALG = "seuntai:konsolidasi_strand"
# lebar koridor (m) -> separuhnya = toleransi algoritma; acuan RUMIJA minimum PP 34/2006 Pasal 40
WIDTHS = [(5.0, "5 m \u2013 exact copies only (cables on both sides of a road stay separate)"),
          (11.0, "11 m \u2013 right-of-way of a small road"),
          (15.0, "15 m \u2013 right-of-way of a medium road (recommended)"),
          (25.0, "25 m \u2013 right-of-way of a main road")]
DEFAULT_WIDTH = 15.0
EMPTY = "<empty>"


def _checked():
    return getattr(Qt, "CheckState", Qt).Checked


def _unchecked():
    return getattr(Qt, "CheckState", Qt).Unchecked


def _user_checkable():
    return getattr(Qt, "ItemFlag", Qt).ItemIsUserCheckable


def _line_layers():
    out = []
    for lyr in QgsProject.instance().mapLayers().values():
        try:
            if isinstance(lyr, QgsVectorLayer) and lyr.isValid() and \
                    QgsWkbTypes.geometryType(lyr.wkbType()) == K.GEOM_LINE:
                out.append(lyr)
        except Exception as _e:
            _log.note(_e)
            continue
    return sorted(out, key=lambda x: x.name().lower())


def _safe(s):
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", s or "").strip("_")[:60] or "data"


class _Feedback(QgsProcessingFeedback):
    """Simpan pesan error/peringatan untuk ditampilkan setelah proses selesai."""

    step = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.errors, self.warnings = [], []

    def setProgressText(self, text):  # noqa: N802 - QGIS API; dipanggil dari thread tugas -> sinyal antre
        self.step.emit(str(text))
        super().setProgressText(text)

    def reportError(self, error, fatalError=False):  # noqa: N802 - QGIS API
        self.errors.append(str(error))
        super().reportError(error, fatalError)

    def pushWarning(self, warning):  # noqa: N802 - QGIS API
        self.warnings.append(str(warning))
        super().pushWarning(warning)


class ConsolidateDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.task = self.ctx = self.fb = None
        self.f_prod = self.f_date = None
        self.setWindowTitle("Seuntai - Consolidate Lines")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        intro = QLabel("Keeps <b>one line per corridor</b>: where lines are stacked or run side by side, only the "
                       "line with the <b>oldest creation date</b> is kept, with its original attributes.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        row = QHBoxLayout()
        row.addWidget(QLabel("Line layer"))
        self.cmb = QComboBox()
        row.addWidget(self.cmb, 1)
        b_open = QPushButton("Open file...")
        b_open.clicked.connect(self.open_file)
        row.addWidget(b_open)
        lay.addLayout(row)

        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setTextFormat(getattr(Qt, "TextFormat", Qt).RichText)
        lay.addWidget(self.info)

        box = QGroupBox("Product / LOB to keep")
        bl = QVBoxLayout(box)
        self.lst = QListWidget()
        self.lst.setMinimumHeight(120)
        bl.addWidget(self.lst)
        br = QHBoxLayout()
        b_all = QPushButton("All")
        b_all.clicked.connect(lambda: self._tick(True))
        b_none = QPushButton("None")
        b_none.clicked.connect(lambda: self._tick(False))
        br.addWidget(b_all)
        br.addWidget(b_none)
        br.addStretch(1)
        bl.addLayout(br)
        lay.addWidget(box)

        roww = QHBoxLayout()
        lw = QLabel("Corridor width")
        lw.setToolTip("Lines closer together than this, along the same route, become one line.")
        roww.addWidget(lw)
        self.cmb_w = QComboBox()
        for w, lab in WIDTHS:
            self.cmb_w.addItem(lab, w)
        try:
            last = float(QgsSettings().value("seuntai/corridor_width", DEFAULT_WIDTH))
        except (TypeError, ValueError):
            last = DEFAULT_WIDTH
        self.cmb_w.setCurrentIndex(max(0, [w for w, _l in WIDTHS].index(last) if last in [w for w, _l in WIDTHS]
                                       else [w for w, _l in WIDTHS].index(DEFAULT_WIDTH)))
        self.cmb_w.setToolTip("Lines closer together than this, along the same route, become one line. Wider = fewer "
                              "side-by-side lines; 5 m keeps cables on opposite sides of a road apart.")
        roww.addWidget(self.cmb_w, 1)
        lay.addLayout(roww)
        self.chk_road = QCheckBox("Match to roads: lines on both sides of the same road become one line "
                                  "(OpenStreetMap, downloaded automatically the first time)")
        self.chk_road.setToolTip("Public OpenStreetMap road centrelines are downloaded once for the area of your data "
                                 "(a few MB per city) and cached. Only the approximate area (11 km road tiles) is "
                                 "requested; your cable data never leaves this computer. Without internet, only the "
                                 "corridor width is used.")
        self.chk_road.setChecked(QgsSettings().value("seuntai/road_matching", "1") != "0")
        lay.addWidget(self.chk_road)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Output folder"))
        self.out = QLineEdit()
        row2.addWidget(self.out, 1)
        b_out = QPushButton("Browse...")
        b_out.clicked.connect(self.pick_out)
        row2.addWidget(b_out)
        lay.addLayout(row2)

        self.chk_open = QCheckBox("Open the report when finished (Indonesian)")
        self.chk_open.setChecked(True)
        lay.addWidget(self.chk_open)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.b_run = QPushButton("Run")
        self.b_run.setDefault(True)
        self.b_run.clicked.connect(self.run)
        b_close = QPushButton("Close")
        b_close.clicked.connect(self.close)
        btns.addWidget(self.b_run)
        btns.addWidget(b_close)
        lay.addLayout(btns)

        self.cmb.currentIndexChanged.connect(self.layer_changed)
        self.reload_layers()

    # ------------------------------------------------------------------ data
    def reload_layers(self, select_id=None):
        self.cmb.blockSignals(True)
        self.cmb.clear()
        active = self.iface.activeLayer()
        sel = 0
        for i, lyr in enumerate(_line_layers()):
            self.cmb.addItem(lyr.name(), lyr.id())
            if (select_id and lyr.id() == select_id) or (not select_id and active is not None and lyr.id() == active.id()):
                sel = i
        self.cmb.blockSignals(False)
        if self.cmb.count():
            self.cmb.setCurrentIndex(sel)
            self.layer_changed()
        else:
            self.info.setText("No line layer in the project. Click <b>Open file...</b> to add one (e.g. a .shp).")
            self.lst.clear()

    def layer(self):
        lid = self.cmb.currentData()
        return QgsProject.instance().mapLayer(lid) if lid else None

    def open_file(self):
        start = QgsSettings().value("seuntai/last_folder", "") or os.path.expanduser("~")
        path, _f = QFileDialog.getOpenFileName(self, "Open line data", start,
                                               "Vector data (*.shp *.gpkg *.geojson *.json *.kml *.kmz *.gml *.fgb)")
        if not path:
            return
        QgsSettings().setValue("seuntai/last_folder", os.path.dirname(path))
        lyr = QgsVectorLayer(path, os.path.splitext(os.path.basename(path))[0], "ogr")
        if not lyr.isValid() or QgsWkbTypes.geometryType(lyr.wkbType()) != K.GEOM_LINE:
            self.status.setText("<span style='color:#B3261E'>This file is not a line layer.</span>")
            return
        QgsProject.instance().addMapLayer(lyr)
        self.reload_layers(lyr.id())

    def layer_changed(self):
        lyr = self.layer()
        self.lst.clear()
        self.status.setText("")
        self.f_prod = self.f_date = None
        if lyr is None:
            return
        fields = lyr.fields()
        names = [f.name() for f in fields]
        if D.is_output_fields(names) or D.is_output_name(lyr.source().split("|")[0]):
            self.info.setText("<span style='color:#B3261E'>This layer is a previous Seuntai result. Pick the original "
                              "data.</span>")
            return
        smp = {nm: [] for nm in names}
        req = QgsFeatureRequest()
        req.setLimit(300)
        try:
            req.setFlags(K.REQ_NOGEOM)
        except Exception as _e:
            _log.note(_e)
        for ft in lyr.getFeatures(req):
            for nm in names:
                smp[nm].append(ft[nm])
        self.f_date, _why = D.pick_date_field([(f.name(), f.typeName()) for f in fields], smp)
        self.f_prod = D.pick_product_field(names)
        counts = {}
        if self.f_prod:
            idx = fields.indexOf(self.f_prod)
            req2 = QgsFeatureRequest()
            try:
                req2.setFlags(K.REQ_NOGEOM)
                req2.setSubsetOfAttributes([idx])
            except Exception as _e:
                _log.note(_e)
            for ft in lyr.getFeatures(req2):
                v = ft[self.f_prod]
                v = "" if v is None or str(v) == "NULL" else str(v).strip()
                counts[v] = counts.get(v, 0) + 1
            for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                it = QListWidgetItem("%s  (%s lines)" % (v or EMPTY, format(n, ",")))
                it.setData(getattr(Qt, "ItemDataRole", Qt).UserRole, v)
                it.setFlags(it.flags() | _user_checkable())
                it.setCheckState(_unchecked())
                self.lst.addItem(it)
            if self.lst.count() == 1:
                self.lst.item(0).setCheckState(_checked())
            self.lst.setEnabled(True)
        else:
            it = QListWidgetItem("No product/LOB column: all lines are used")
            self.lst.addItem(it)
            self.lst.setEnabled(False)
        msg = ["Product/LOB column: <b>%s</b>" % (self.f_prod or "none")]
        if self.f_date:
            msg.append("Creation-date column: <b>%s</b> (oldest line kept)" % self.f_date)
        else:
            msg.append("<span style='color:#B54708'><b>Warning: no creation-date column.</b> Stacked lines are still "
                       "reduced to one, but the oldest line cannot be determined: the <b>longest</b> line is kept and "
                       "the results are marked <code>_TANPA_TANGGAL</code> / <code>su_dasar = PANJANG</code>.</span>")
        self.info.setText("<br>".join(msg))
        src = lyr.source().split("|")[0]
        base = os.path.dirname(src) if os.path.exists(src) else (QgsSettings().value("seuntai/last_folder", "")
                                                                  or os.path.expanduser("~"))
        self.out.setText(os.path.join(base, "Hasil_Seuntai", _safe(lyr.name())))

    def _tick(self, on):
        if not self.lst.isEnabled():
            return
        for i in range(self.lst.count()):
            self.lst.item(i).setCheckState(_checked() if on else _unchecked())

    def pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.out.text() or os.path.expanduser("~"))
        if d:
            self.out.setText(d)

    def chosen(self):
        role = getattr(Qt, "ItemDataRole", Qt).UserRole
        on, total = [], 0
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            total += 1
            if it.checkState() == _checked():
                on.append(it.data(role))
        return on, total

    # ------------------------------------------------------------------ jalankan
    def run(self):
        lyr = self.layer()
        if lyr is None:
            self.status.setText("<span style='color:#B3261E'>Pick a line layer first.</span>")
            return
        values = ""
        if self.f_prod:
            on, total = self.chosen()
            if not on:
                self.status.setText("<span style='color:#B3261E'>Tick at least one product/LOB value.</span>")
                return
            if len(on) < total:
                if "" in on:
                    self.status.setText("<span style='color:#B3261E'>Lines with an empty product value can only be "
                                        "kept together with all values (click All).</span>")
                    return
                values = ",".join(on)
        width = float(self.cmb_w.currentData() or DEFAULT_WIDTH)
        QgsSettings().setValue("seuntai/corridor_width", width)
        QgsSettings().setValue("seuntai/road_matching", "1" if self.chk_road.isChecked() else "0")
        outdir = self.out.text().strip()
        if not outdir:
            self.status.setText("<span style='color:#B3261E'>Choose an output folder.</span>")
            return
        os.makedirs(outdir, exist_ok=True)
        tag = _safe(lyr.name() + ("_" + values.replace(",", "_") if values else ""))
        params = {"INPUT": lyr.id(), "FIELD_PRODUCT": self.f_prod or None, "PRODUCT_VALUES": values,
                  "FIELD_DATE": self.f_date or None, "SKIP_NO_DATE": False,
                  "SINGLE_LINES": "TEMPORARY_OUTPUT", "OUTPUT": "TEMPORARY_OUTPUT", "SEGMENTS": "TEMPORARY_OUTPUT",
                  "NOTES": "TEMPORARY_OUTPUT", "REPORT": os.path.join(outdir, "Laporan_Seuntai_%s.html" % tag),
                  "SHP_FOLDER": outdir, "OPEN_REPORT": False, "TOLERANCE": width / 2.0,
                  "ROAD_MATCHING": 0 if self.chk_road.isChecked() else 1}
        alg = QgsApplication.processingRegistry().createAlgorithmById(ALG)
        if alg is None:
            self.status.setText("<span style='color:#B3261E'>Seuntai algorithm not found; restart QGIS.</span>")
            return
        self.ctx = QgsProcessingContext()
        self.ctx.setProject(QgsProject.instance())
        self.fb = _Feedback()
        self.fb.progressChanged.connect(lambda p: self.bar.setValue(int(p)))
        self.fb.step.connect(lambda t: self.status.setText("Running... %s<br><span style='color:#666'>QGIS stays "
                                                           "usable; results are loaded when finished.</span>" % t))
        self._busy = True
        self.task = QgsProcessingAlgRunnerTask(alg, params, self.ctx, self.fb)
        self.task.executed.connect(self.run_finished)
        self.b_run.setEnabled(False)
        self.bar.setValue(0)
        self.bar.setVisible(True)
        self.status.setText("Running... QGIS stays usable; results are loaded when finished.")
        QgsApplication.taskManager().addTask(self.task)

    def run_finished(self, ok, results=None):
        # bukan 'done': nama itu milik QDialog.done(int) yang dipanggil close(); hasil diproses sekali saja
        if not getattr(self, "_busy", False) or (ok and not isinstance(results, dict)):
            return
        self._busy = False
        results = results or {}
        self.b_run.setEnabled(True)
        self.bar.setVisible(False)
        if not ok:
            err = (self.fb.errors[-1] if self.fb and self.fb.errors else "unknown error")
            self.status.setText("<span style='color:#B3261E'><b>Failed:</b> %s</span>" % err[:600])
            return
        shp = results.get("SHP_KABEL") or ""
        nodate = results.get("DASAR_URUTAN") == "PANJANG"
        if shp and os.path.exists(shp):
            name = os.path.splitext(os.path.basename(shp))[0]
            lyr = QgsVectorLayer(shp, name, "ogr")
            if lyr.isValid():
                try:
                    lyr.setRenderer(QgsSingleSymbolRenderer(styles.kabel_symbol()))
                except Exception as _e:
                    _log.note(_e)
                QgsProject.instance().addMapLayer(lyr)
        txt = ("<b>Done.</b> %s lines in -> %s single lines (one per corridor), %s duplicates removed.<br>"
               "Shapefile: %s" % (format(int(results.get("N_INPUT") or 0), ","),
                                  format(int(results.get("N_KABEL") or 0), ","),
                                  format(int(results.get("N_DUPLIKAT") or 0), ","), shp or "-"))
        if nodate:
            txt += ("<br><span style='color:#B54708'><b>No creation date:</b> the longest line was kept per corridor "
                    "(marked _TANPA_TANGGAL).</span>")
        elif results.get("TERTUA"):
            txt += "<br>Oldest kept cable: %s" % results.get("TERTUA")
        road_w = [w for w in (self.fb.warnings if self.fb else []) if w.startswith("Road matching")]
        if road_w:
            txt += "<br><span style='color:#B54708'>%s</span>" % road_w[-1][:300]
        self.status.setText(txt)
        try:
            self.iface.messageBar().pushSuccess("Seuntai", "Consolidated: %s" % (os.path.basename(shp) or "done"))
        except Exception as _e:
            _log.note(_e)
        rpt = results.get("REPORT")
        if self.chk_open.isChecked() and rpt and os.path.exists(rpt):
            QDesktopServices.openUrl(QUrl.fromLocalFile(rpt))
