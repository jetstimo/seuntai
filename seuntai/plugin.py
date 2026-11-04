# -*- coding: utf-8 -*-
# Seuntai - Strand Consolidator - menu, toolbar, and Processing registration
# Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-3.0-or-later with section 7 terms (see LICENSE).
import os

from qgis.core import QgsApplication, QgsSettings, QgsVectorLayer, QgsProject
from qgis.PyQt.QtGui import QIcon

try:                                    # Qt6 / QGIS 4
    from qgis.PyQt.QtGui import QAction
except ImportError:                     # Qt5 / QGIS 3
    from qgis.PyQt.QtWidgets import QAction

from .provider import SeuntaiProvider
from . import _log

MENU = "&Seuntai"
HERE = os.path.dirname(__file__)


class SeuntaiPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.actions = []
        self.dlg = None

    def initProcessing(self):  # noqa: N802 - QGIS API
        self.provider = SeuntaiProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def _add(self, label, tip, slot, toolbar=False):
        act = QAction(QIcon(os.path.join(HERE, "icon.png")), label, self.iface.mainWindow())
        act.setToolTip(tip)
        act.setStatusTip(tip)
        act.triggered.connect(slot)
        if toolbar:
            self.iface.addToolBarIcon(act)
        self.iface.addPluginToVectorMenu(MENU, act)
        self.actions.append(act)
        return act

    def initGui(self):  # noqa: N802 - QGIS API
        self.initProcessing()
        self._add("Consolidate Lines...",
                  "Pick a line layer and the product/LOB: stacked lines become one line per corridor (oldest kept)",
                  self.consolidate, toolbar=True)
        self._add("Consolidate a Folder...",
                  "Pick a folder: every line dataset in it is found and consolidated with the same rules",
                  lambda checked=False: self.run("seuntai:otomatis"))
        self._add("Check Stacked Corridors...",
                  "Report duplicates, partly parallel lines, gaps and junctions without changing the data",
                  lambda checked=False: self.run("seuntai:periksa_koridor_ganda"))
        self._add("Load Sample Data", "Add a small sample layer of stacked lines to try Seuntai", self.sample)
        self._add("Base Map...", "Background for checking results: satellite imagery (sharp, native zoom detected "
                  "automatically), street map or none. One layer shared with Seranta; only tiles on screen are "
                  "downloaded and cached", self.base_map)
        self._add("About Seuntai", "Version, authors and license", self.about)
        st = QgsSettings()
        if st.value("seuntai/welcomed2", "") != "1":
            st.setValue("seuntai/welcomed2", "1")
            try:
                self.iface.messageBar().pushInfo(
                    "Seuntai", "Installed. Click the Seuntai toolbar icon, pick a line layer and the product, then Run.")
            except Exception as _e:
                _log.note(_e)

    def unload(self):
        if self.dlg is not None:
            try:
                self.dlg.close()
                self.dlg.deleteLater()
            except Exception as _e:
                _log.note(_e)
            self.dlg = None
        for act in self.actions:
            self.iface.removePluginVectorMenu(MENU, act)
            try:
                self.iface.removeToolBarIcon(act)
            except Exception as _e:
                _log.note(_e)
        self.actions = []
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None

    def consolidate(self):
        from .dialog import ConsolidateDialog
        if self.dlg is None:
            self.dlg = ConsolidateDialog(self.iface)
        else:
            self.dlg.reload_layers()
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()

    def run(self, alg):
        import processing
        params = {}
        lyr = self.iface.activeLayer()
        if alg == "seuntai:otomatis":
            folder = ""
            try:
                src = lyr.source().split("|")[0] if isinstance(lyr, QgsVectorLayer) else ""
                if src and os.path.exists(src):
                    folder = os.path.dirname(src)
            except Exception:
                folder = ""
            if not folder:
                last = QgsSettings().value("seuntai/last_folder", "")
                dl = os.path.join(os.path.expanduser("~"), "Downloads")
                folder = last if last and os.path.isdir(last) else (dl if os.path.isdir(dl) else "")
            if folder:
                params["FOLDER"] = folder
                QgsSettings().setValue("seuntai/last_folder", folder)
            processing.execAlgorithmDialog(alg, params)
            return
        try:
            from qgis.core import QgsWkbTypes
            from .compat import GEOM_LINE
            if isinstance(lyr, QgsVectorLayer) and QgsWkbTypes.geometryType(lyr.wkbType()) == GEOM_LINE:
                params["INPUT"] = lyr.id()
        except Exception as _e:
            _log.note(_e)
        processing.execAlgorithmDialog(alg, params)

    def sample(self):
        p = os.path.join(HERE, "contoh", "contoh_multiline_fttt.geojson")
        lyr = QgsVectorLayer(p, "Seuntai sample (stacked lines)", "ogr")
        if lyr.isValid():
            QgsProject.instance().addMapLayer(lyr)
            self.iface.setActiveLayer(lyr)
            try:
                self.iface.mapCanvas().setExtent(self.iface.mapCanvas().mapSettings().layerExtentToOutputExtent(
                    lyr, lyr.extent()))
                self.iface.mapCanvas().refresh()
            except Exception as _e:
                _log.note(_e)

    def base_map(self):
        from qgis.PyQt.QtWidgets import QInputDialog
        from . import basemap
        keys = list(basemap.CHOICES)
        cur = keys.index(basemap.choice())
        item, ok = QInputDialog.getItem(self.iface.mainWindow(), "Seuntai - Base map", "Background map:",
                                        [basemap.LABELS[k] for k in keys], cur, False)
        if not ok:
            return
        kind = keys[[basemap.LABELS[k] for k in keys].index(item)]
        basemap.set_choice(kind)
        ms = self.iface.mapCanvas().mapSettings()
        basemap.ensure(kind, ms.extent(), ms.destinationCrs())

    def about(self):
        from qgis.PyQt.QtWidgets import QMessageBox
        from .alg_strand import __version__, __author__, integrity_status
        box = QMessageBox(self.iface.mainWindow())
        box.setWindowTitle("Seuntai")
        box.setText(
            "<b>Seuntai&trade; - Strand Consolidator</b> v%s<br>Authors: %s<br>File integrity: %s<br><br>"
            "Turns stacked or parallel lines in one corridor into a single line: the line with the oldest creation "
            "date is kept, with its original attributes, for the product/LOB you choose. Reports are in Indonesian."
            "<br><br>License: GNU GPL v3 or later with the section 7 terms in LICENSE: copies and modifications must "
            "keep both authors' names, modified versions must be renamed and marked as modified and may not claim "
            "authorship. Official releases are digitally signed; the official release key fingerprint is "
            "<b>92C4-D078-D1FC-1C5B</b> (also published on plugins.qgis.org and github.com/jetstimo/seuntai). "
            "Seuntai&trade; is a trademark of Joseph Edward Timothy Siahaan and Sidah Fahira. "
            "Fonts Inter and IBM Plex Mono: SIL OFL 1.1. Leaflet: BSD-2-Clause."
            % (__version__, __author__, integrity_status(en=True)))
        role = getattr(getattr(QMessageBox, "ButtonRole", QMessageBox), "ActionRole")
        ok = getattr(getattr(QMessageBox, "StandardButton", QMessageBox), "Ok")
        ver_b = box.addButton("Verify online", role)
        box.addButton(ok)
        (box.exec if hasattr(box, "exec") else box.exec_)()
        if box.clickedButton() is ver_b:
            self._verify_online()

    def _verify_online(self):
        """Cocokkan salinan terpasang dengan RILIS_RESMI.json di GitHub pembuat (lewat proxy QGIS)."""
        from qgis.PyQt.QtWidgets import QMessageBox
        from . import keaslian

        def fetch(url):
            from qgis.core import QgsBlockingNetworkRequest
            from qgis.PyQt.QtCore import QUrl
            from qgis.PyQt.QtNetwork import QNetworkRequest
            req = QgsBlockingNetworkRequest()
            err = req.get(QNetworkRequest(QUrl(url)), True)
            if err != getattr(QgsBlockingNetworkRequest, "NoError", 0):
                raise IOError(req.errorMessage())
            return bytes(req.reply().content())
        try:
            code, text = keaslian.verify_online(fetch)
        except Exception as e:      # verifikasi tidak boleh membuat QGIS galat
            code, text = "GAGAL", str(e)[:120]
        title = "Official release verified" if code == "TERVERIFIKASI" else "Not verified"
        (QMessageBox.information if code == "TERVERIFIKASI" else QMessageBox.warning)(
            self.iface.mainWindow(), "Seuntai - " + title, text)
