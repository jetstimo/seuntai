# -*- coding: utf-8 -*-
# Seuntai - Processing provider
# Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-2.0-or-later (see LICENSE).
import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .alg_strand import KonsolidasiStrand, PeriksaKoridor, __version__
from .batch import OtomatisSeuntai


class SeuntaiProvider(QgsProcessingProvider):
    """Mengelompokkan alat Seuntai di Processing Toolbox."""

    def id(self):
        return "seuntai"

    def name(self):
        return "Seuntai"

    def longName(self):
        return "Seuntai - Strand Consolidator v%s" % __version__

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))

    def loadAlgorithms(self):
        self.addAlgorithm(OtomatisSeuntai())
        self.addAlgorithm(KonsolidasiStrand())
        self.addAlgorithm(PeriksaKoridor())
