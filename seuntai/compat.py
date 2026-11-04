# -*- coding: utf-8 -*-
"""Seuntai - kompatibilitas QGIS 3.22 LTR sampai QGIS 4.x (Qt5/Qt6): nama enum berubah antar versi.
Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-3.0-or-later with section 7 terms (see LICENSE)."""
from qgis.core import (Qgis, QgsFeatureRequest, QgsFeatureSink, QgsField, QgsProcessing, QgsProcessingParameterDefinition,
                       QgsProcessingParameterField, QgsProcessingParameterNumber, QgsUnitTypes, QgsVectorFileWriter,
                       QgsWkbTypes)


def _enum(*cands):
    ns = {"Qgis": Qgis, "QgsWkbTypes": QgsWkbTypes, "QgsProcessing": QgsProcessing, "QgsUnitTypes": QgsUnitTypes,
          "QgsProcessingParameterDefinition": QgsProcessingParameterDefinition,
          "QgsProcessingParameterField": QgsProcessingParameterField,
          "QgsProcessingParameterNumber": QgsProcessingParameterNumber, "QgsFeatureSink": QgsFeatureSink,
          "QgsVectorFileWriter": QgsVectorFileWriter, "QgsFeatureRequest": QgsFeatureRequest}
    for c in cands:
        parts = c.split(".")
        obj = ns.get(parts[0])
        for p in parts[1:]:
            obj = getattr(obj, p, None) if obj is not None else None
        if obj is not None:
            return obj
    raise AttributeError("Enum tidak ditemukan: %s" % (cands,))


SRC_LINE = _enum("Qgis.ProcessingSourceType.VectorLine", "QgsProcessing.TypeVectorLine")
SRC_POINT = _enum("Qgis.ProcessingSourceType.VectorPoint", "QgsProcessing.TypeVectorPoint")
NUM_DOUBLE = _enum("Qgis.ProcessingNumberParameterType.Double", "QgsProcessingParameterNumber.Double")
NUM_INT = _enum("Qgis.ProcessingNumberParameterType.Integer", "QgsProcessingParameterNumber.Integer")
REQ_NOGEOM = _enum("Qgis.FeatureRequestFlag.NoGeometry", "QgsFeatureRequest.NoGeometry")
FIELD_ANY = _enum("Qgis.ProcessingFieldParameterDataType.Any", "QgsProcessingParameterField.Any")
FLAG_ADV = _enum("Qgis.ProcessingParameterFlag.Advanced", "QgsProcessingParameterDefinition.FlagAdvanced")
WKB_MLINE = _enum("Qgis.WkbType.MultiLineString", "QgsWkbTypes.MultiLineString")
WKB_POINT = _enum("Qgis.WkbType.Point", "QgsWkbTypes.Point")
GEOM_LINE = _enum("Qgis.GeometryType.Line", "QgsWkbTypes.LineGeometry")
FAST = _enum("QgsFeatureSink.Flag.FastInsert", "QgsFeatureSink.FastInsert")
WRITER_OK = _enum("QgsVectorFileWriter.WriterError.NoError", "QgsVectorFileWriter.NoError")
UNIT_M = _enum("Qgis.DistanceUnit.Meters", "QgsUnitTypes.DistanceMeters")

# Tipe kolom: QGIS 3.38+ dan QGIS 4 memakai QMetaType; versi lama memakai QVariant.
try:
    from qgis.PyQt.QtCore import QMetaType
    T_STR, T_INT, T_DBL = QMetaType.Type.QString, QMetaType.Type.Int, QMetaType.Type.Double
    QgsField("x", T_STR)
except Exception:  # QGIS < 3.38
    from qgis.PyQt.QtCore import QVariant
    T_STR, T_INT, T_DBL = QVariant.String, QVariant.Int, QVariant.Double


def field(name, typ, length=0):
    f = QgsField(name, typ)
    if length:
        f.setLength(length)
    return f


def advanced(param):
    param.setFlags(param.flags() | FLAG_ADV)
    return param
