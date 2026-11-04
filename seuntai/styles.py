# -*- coding: utf-8 -*-
"""Seuntai - gaya otomatis untuk layer keluaran.
Warna status memakai palet Okabe-Ito (Color Universal Design) agar tetap terbedakan oleh pengguna buta warna;
status juga dibedakan dengan pola garis (utuh/putus-putus/titik), bukan warna saja.
Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-3.0-or-later with section 7 terms (see LICENSE)."""
from . import _log
try:
    from qgis.core import (QgsCategorizedSymbolRenderer, QgsLineSymbol, QgsMarkerSymbol,
                           QgsProcessingLayerPostProcessorInterface, QgsRendererCategory, QgsSingleSymbolRenderer)
except ImportError:  # di luar QGIS
    QgsProcessingLayerPostProcessorInterface = object

# Okabe & Ito (2008) Color Universal Design
OI = {"orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "yellow": "#F0E442", "blue": "#0072B2",
      "vermillion": "#D55E00", "purple": "#CC79A7", "black": "#000000"}
BRAND = {"ink": "#1A1033", "coral": "#FF4D6D", "amber": "#FFB703", "lilac": "#A898FF", "mint": "#2EE6A6"}

SEG_STYLE = [  # status, warna, lebar mm, pola, label
    ("DIPAKAI", OI["green"], 0.9, "solid", "Dipakai utuh"),
    ("DIPANGKAS", OI["orange"], 0.8, "dash", "Dipangkas (bagian paralel dibuang)"),
    ("DUPLIKAT", OI["vermillion"], 0.6, "dot", "Duplikat (dibuang)"),
    ("SERPIHAN", OI["purple"], 0.6, "dot", "Serpihan pendek (dibuang)"),
    ("GEOMETRI_KOSONG", "#8C8C8C", 0.4, "dot", "Tanpa geometri"),
]
NOTE_STYLE = [  # jenis, bentuk, warna, ukuran mm, label, tampil awal
    ("CELAH", "triangle", OI["vermillion"], 3.0, "Celah antar-untai (perlu dicek)", True),
    ("JEMBATAN", "diamond", OI["yellow"], 2.4, "Celah dijembatani", True),
    ("CABANG", "square", OI["blue"], 2.0, "Percabangan", False),
    ("UJUNG", "circle", OI["black"], 1.6, "Ujung untai", False),
]


def strand_symbol():
    sym = QgsLineSymbol.createSimple({"line_color": BRAND["ink"], "line_width": "2.2", "line_width_unit": "MM",
                                      "capstyle": "round", "joinstyle": "round"})
    top = QgsLineSymbol.createSimple({"line_color": BRAND["coral"], "line_width": "1.3", "line_width_unit": "MM",
                                      "capstyle": "round", "joinstyle": "round"})
    core = QgsLineSymbol.createSimple({"line_color": BRAND["amber"], "line_width": "0.35", "line_width_unit": "MM",
                                       "capstyle": "round", "joinstyle": "round"})
    sym.appendSymbolLayer(top.symbolLayer(0).clone())
    sym.appendSymbolLayer(core.symbolLayer(0).clone())
    return sym


def kabel_symbol():
    """Kabel tunggal: garis koral dengan tepi ungu tua - lapisan utama yang dilihat pengguna."""
    sym = QgsLineSymbol.createSimple({"line_color": BRAND["ink"], "line_width": "1.5", "line_width_unit": "MM",
                                      "capstyle": "round", "joinstyle": "round"})
    top = QgsLineSymbol.createSimple({"line_color": BRAND["coral"], "line_width": "0.8", "line_width_unit": "MM",
                                      "capstyle": "round", "joinstyle": "round"})
    sym.appendSymbolLayer(top.symbolLayer(0).clone())
    return sym


def segment_renderer():
    cats = []
    for val, col, w, style, label in SEG_STYLE:
        s = QgsLineSymbol.createSimple({"line_color": col, "line_width": str(w), "line_width_unit": "MM",
                                        "line_style": style, "capstyle": "round"})
        cats.append(QgsRendererCategory(val, s, label))
    return QgsCategorizedSymbolRenderer("su_status", cats)


def note_renderer():
    cats = []
    for val, shape, col, size, label, show in NOTE_STYLE:
        s = QgsMarkerSymbol.createSimple({"name": shape, "color": col, "size": str(size), "size_unit": "MM",
                                          "outline_color": "#ffffff", "outline_width": "0.3"})
        # percabangan & ujung bisa ribuan pada jaringan besar: ada di legenda, dimatikan agar peta terbaca
        cats.append(QgsRendererCategory(val, s, label, show))
    return QgsCategorizedSymbolRenderer("jenis", cats)


_PENDING = []


def _hide_later(layer_id, delay=500):
    """Matikan centang layer di panel Layers (layer tetap ada). Dipakai untuk layer pendukung agar peta tidak
    menampilkan garis bertumpuk."""
    try:
        from qgis.core import QgsProject
        from qgis.PyQt.QtCore import QTimer

        def go():
            try:
                node = QgsProject.instance().layerTreeRoot().findLayer(layer_id)
                if node is not None:
                    node.setItemVisibilityChecked(False)
            except Exception as _e:
                _log.note(_e)
            finally:
                if go in _PENDING:
                    _PENDING.remove(go)
        _PENDING.append(go)
        QTimer.singleShot(delay, go)
    except Exception as _e:
        _log.note(_e)


def _to_top_later(layer_id, delay=300):
    """Pindahkan layer untai ke paling atas daftar layer setelah semua keluaran dimuat (untai harus terlihat)."""
    try:
        from qgis.core import QgsProject
        from qgis.PyQt.QtCore import QTimer

        def go():
            try:
                root = QgsProject.instance().layerTreeRoot()
                node = root.findLayer(layer_id)
                if node is not None:
                    parent = node.parent()
                    parent.insertChildNode(0, node.clone())
                    parent.removeChildNode(node)
            except Exception as _e:
                _log.note(_e)
            finally:
                if go in _PENDING:
                    _PENDING.remove(go)
        _PENDING.append(go)
        QTimer.singleShot(delay, go)
    except Exception as _e:
        _log.note(_e)


class PostProcessor(QgsProcessingLayerPostProcessorInterface):
    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    def postProcessLayer(self, layer, context, feedback):  # noqa: N802 - QGIS API
        try:
            if self.kind == "kabel":
                layer.setRenderer(QgsSingleSymbolRenderer(kabel_symbol()))
                _to_top_later(layer.id(), 350)
            elif self.kind == "strand":
                layer.setRenderer(QgsSingleSymbolRenderer(strand_symbol()))
                _hide_later(layer.id())
            elif self.kind == "segmen":
                layer.setRenderer(segment_renderer())
                layer.setOpacity(0.75)
                _hide_later(layer.id())
            elif self.kind == "catatan":
                layer.setRenderer(note_renderer())
                _to_top_later(layer.id(), 450)      # titik catatan di atas untai
            layer.triggerRepaint()
        except Exception as e:  # gaya hanya kosmetik
            try:
                feedback.pushInfo("Layer style not applied: %r" % e)
            except Exception as _e:
                _log.note(_e)
