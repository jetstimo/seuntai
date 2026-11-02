# -*- coding: utf-8 -*-
"""
Seuntai - algoritma Processing:
  1. Konsolidasi Strand (banyak garis koridor -> 1 untai)
  2. Periksa Koridor Ganda (hanya laporan, data tidak diubah)

Pengembangan dari dokumen kebutuhan "Attribute-Based Strand Consolidator":
filter atribut (produk/LOB), prioritas CREATEDATE tertua, Dissolve + Line Merge. Perbedaan penting dari
skrip panduan dijelaskan di DASAR_KEPUTUSAN.md (kesamaan koridor diukur dengan jarak, bukan WKT identik;
tanggal tak terbaca tidak lagi dianggap tertua; noding sebelum line merge; laporan dan jejak keputusan).

Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-2.0-or-later (see LICENSE).
"""
import datetime as _dt
import math
import os
import time

from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDistanceArea, QgsExpression,
                       QgsFeature, QgsField,
                       QgsFeatureRequest, QgsFields, QgsGeometry, QgsPointXY, QgsProcessingAlgorithm,
                       QgsProcessingException,
                       QgsProcessingOutputNumber, QgsProcessingOutputString, QgsProcessingParameterBoolean, QgsProcessingParameterEnum,
                       QgsProcessingParameterExpression, QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
                       QgsProcessingParameterFileDestination, QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterNumber, QgsVectorFileWriter,
                       QgsProcessingParameterString, QgsWkbTypes)
from qgis.PyQt.QtGui import QIcon

from . import core as C
from . import compat as K
from . import report
from . import styles
from . import deteksi as D

__product__ = "Seuntai"
__version__ = "2.0.0"
__author__ = "Joseph Edward Timothy Siahaan, Sidah Fahira"
HERE = os.path.dirname(__file__)

# Label isian (Inggris) dan padanannya di laporan (Indonesia); urutan = nilai enum, tidak boleh diubah.
MODES = ["Trim the parallel part and join the rest (recommended)",
         "Keep whole lines per corridor (no cutting)",
         "Merge everything like the reference script (only exact duplicates removed)"]
MODES_ID = ["Pangkas bagian paralel lalu sambung (disarankan)",
            "Pilih garis utuh per koridor (tanpa memotong)",
            "Gabung semua seperti skrip panduan (hanya buang yang identik)"]
PRIORITAS = ["Oldest creation date first", "Newest creation date first"]
PRIORITAS_ID = ["Tanggal tertua dulu (CREATEDATE paling lama)", "Tanggal terbaru dulu"]
KELUARAN = ["One feature per strand (all connected pieces)", "One feature per piece (split at junctions)"]
KELUARAN_ID = ["Satu fitur per untai (semua ruas yang tersambung)", "Satu fitur per ruas (dipisah di percabangan)"]
NODATE_TAG = "TANPA_TANGGAL"
ROAD_MODES = ["Automatic: OpenStreetMap roads (downloaded once, then cached)", "Off: distance corridor only"]
ROAD_MODES_ID = ["Otomatis: jalan OpenStreetMap (diunduh sekali, lalu disimpan)", "Tidak dipakai: koridor jarak saja"]     # penanda nama berkas hasil bila tidak ada kolom tanggal pembuatan


def _norm(s):
    return "".join(ch for ch in str(s or "").upper() if ch.isalnum())


PRODUCT_ALIASES = ("PRODUCT", "LOB", "PRODUK", "LINE_OF_BUSINESS", "PRODUCT_LOB")


def resolve_field(fields, name):
    """Cari kolom tanpa membedakan huruf besar/kecil, spasi, atau garis bawah (PRODUCT = product = Product)."""
    if not name:
        return None
    names = [f.name() for f in fields]
    if name in names:
        return name
    n = _norm(name)
    for nm in names:
        if _norm(nm) == n:
            return nm
    return False


def utm_for(lon, lat):
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    zone = min(max(zone, 1), 60)
    return QgsCoordinateReferenceSystem("EPSG:%d" % ((32600 if lat >= 0 else 32700) + zone))




SLOT = 1.0e7     # geseran x antar-zona: koordinat kerja = easting UTM + nomor_slot x 10.000 km (tidak tumpang tindih)


def slot_offset(code):
    """Geseran x tetap untuk satu kode EPSG UTM (326zz utara -> slot zz, 327zz selatan -> slot 60+zz)."""
    return SLOT * ((code - 32600) if code < 32700 else (code - 32700 + 60))


def slot_of(x):
    """Kode EPSG UTM dari koordinat x kerja yang sudah digeser."""
    s = int(math.floor((x + SLOT / 2.0) / SLOT))
    return 32600 + s if s <= 60 else 32700 + (s - 60)


def _attr_uid(f):
    """Atribut fitur sebagai teks: pemutus seri terakhir (setelah tanggal, panjang, geometri) yang tidak bergantung
    pada FID, sehingga pilihan di antara dua garis kembar tetap sama walau berkas dipotong/digabung."""
    try:
        return "|".join("" if v is None else str(v) for v in f.attributes())
    except Exception:
        return ""


def _xy_parts(g):
    """QgsGeometry garis -> [[(x, y), ...], ...]; kurva diubah menjadi segmen lurus, Z/M diabaikan."""
    if g is None or g.isNull() or g.isEmpty():
        return []
    g = QgsGeometry(g)
    try:
        if QgsWkbTypes.isCurvedType(g.wkbType()):
            g.convertToStraightSegment()
    except Exception:
        pass
    if QgsWkbTypes.geometryType(g.wkbType()) != K.GEOM_LINE:
        return []
    try:
        if g.isMultipart():
            lines = g.asMultiPolyline()
        else:
            lines = [g.asPolyline()]
    except Exception:
        return []
    return [[(p.x(), p.y()) for p in ln] for ln in lines if len(ln) >= 2]


def _mline(parts):
    return QgsGeometry.fromMultiPolylineXY([[QgsPointXY(x, y) for x, y in p] for p in parts])


def _fmt_date(d):
    if d is None:
        return ""
    if d.hour or d.minute or d.second:
        return d.strftime("%Y-%m-%d %H:%M:%S")
    return d.strftime("%Y-%m-%d")


def _short_list(items, limit=240):
    s = ",".join(str(i) for i in items)
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(",", 1)[0]
    return cut + ",...(+%d)" % (len(items) - cut.count(",") - 1)


def write_shp(path, fields, wkb, crs, feats, context):
    """Tulis fitur ke Shapefile (ESRI Shapefile, UTF-8). Menimpa berkas lama dengan nama yang sama."""
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "ESRI Shapefile"
    opts.fileEncoding = "UTF-8"
    w = QgsVectorFileWriter.create(path, fields, wkb, crs, context.transformContext(), opts)
    if w.hasError() != K.WRITER_OK:
        msg = w.errorMessage()
        del w
        raise QgsProcessingException(msg)
    for f in feats:
        w.addFeature(f)
    del w


def oldest_rows(rows, feats, f_id, f_prod, sid_of_fid, n=10):
    """10 kabel terpilih dengan tanggal pembuatan tertua (untuk laporan)."""
    dated = sorted((r for r in rows if r.date is not None), key=lambda r: (r.date, r.rank))[:n]
    out = []
    for r in dated:
        f = feats[r.fid]

        def val(fn):
            if not fn:
                return ""
            v = f[fn]
            return "" if v is None or str(v) == "NULL" else str(v)
        out.append({"fid": r.fid, "tanggal": _fmt_date(r.date), "nama": val(f_id), "produk": val(f_prod),
                    "panjang": r.len_e, "status": r.status, "untai": sid_of_fid.get(r.fid, "")})
    return out


ROAD_HALF_M = 2.75      # separuh badan jalan kecil 2 x 2,75 m (Permen PU 19/2011)
DEFAULT_TOL = 7.5       # separuh koridor 15 m = RUMIJA minimum jalan sedang (PP 34/2006 Pasal 40)
RUMIJA_M = (("jalan kecil", "small road", 11.0), ("jalan sedang", "medium road", 15.0),
            ("jalan raya", "main road", 25.0), ("jalan bebas hambatan", "freeway", 30.0))


def _en(x, d=1):
    """Angka untuk pesan berbahasa Inggris (titik desimal)."""
    return ("%%.%df" % d) % x if x is not None else "-"


def tolerance_checks(tol, profile, en=False):
    """Nilai toleransi terhadap data (lutut kurva jarak) dan geometri jalan. Hasil: [(level, pesan)].
    en=True: pesan Inggris untuk log Processing (laporan HTML tetap berbahasa Indonesia)."""
    out = []
    width = 2.0 * tol
    if width > RUMIJA_M[-1][2]:
        out.append(("W", ("Corridor %s m is wider than the right-of-way of a freeway (30 m): separate roads running "
                          "side by side may be merged into one route." % _en(width, 1)) if en else
                    ("Koridor %s m lebih lebar dari RUMIJA jalan bebas hambatan (30 m): jalan berbeda yang berdampingan "
                     "bisa ikut dianggap satu jalur." % C._id(width, 1))))
    elif width < RUMIJA_M[0][2]:
        out.append(("I", ("Corridor %s m is narrower than the right-of-way of a small road (11 m): cables on both sides "
                          "of a road stay separate, and lines drawn more than %s m apart remain side by side."
                          % (_en(width, 1), _en(tol, 1))) if en else
                    ("Koridor %s m lebih sempit dari RUMIJA jalan kecil (11 m): kabel di dua sisi jalan tetap terpisah, "
                     "dan garis yang digambar lebih dari %s m berjauhan tetap tampak berdampingan."
                     % (C._id(width, 1), C._id(tol, 1)))))
    else:
        nm = [r for r in RUMIJA_M if r[2] <= width + 1e-9][-1]
        out.append(("I", ("Corridor %s m covers the right-of-way of a %s (%s m): lines up to %s m apart along the same "
                          "road become one line." % (_en(width, 1), nm[1], _en(nm[2], 0), _en(tol, 1))) if en else
                    ("Koridor %s m mencakup RUMIJA %s (%s m): garis yang berjarak sampai %s m di jalan yang sama "
                     "dijadikan satu." % (C._id(width, 1), nm[0], C._id(nm[2], 0), C._id(tol, 1)))))
    if profile and profile.get("knee") is not None:
        kn = profile["knee"]
        share = C.cum_at(profile, tol)
        if tol < kn:
            out.append(("W", ("Tolerance %s m is below the knee of the data's distance curve (%s m): many parallel "
                              "line pairs are not caught yet." % (_en(tol, 2), _en(kn, 1))) if en else
                        ("Toleransi %s m lebih kecil dari lutut kurva jarak data (%s m): sebagian besar pasangan "
                         "garis sejajar belum tertangkap." % (C._id(tol, 2), C._id(kn, 1)))))
        else:
            out.append(("I", ("Tolerance %s m >= knee of the data's distance curve (%s m); %s%% of the line length "
                              "has another line within the tolerance." % (_en(tol, 2), _en(kn, 1),
                                                                         _en(share or 0, 1))) if en else
                        ("Toleransi %s m >= lutut kurva jarak data (%s m); %s%% panjang garis punya garis lain "
                         "dalam jarak toleransi." % (C._id(tol, 2), C._id(kn, 1), C._id(share or 0, 1)))))
    return out


class _LayerRoads:
    """Layer garis tengah jalan milik pengguna sebagai pengganti OpenStreetMap. Kelas diambil dari kolom 'highway' /
    'fclass' (format OSM/Geofabrik) atau kata kunci RBI (arteri, kolektor, lokal, lingkungan, setapak)."""
    KEYS = (("tol", None), ("bebas hambatan", None), ("arteri", "primary"), ("kolektor", "secondary"),
            ("lokal", "tertiary"), ("lingkungan", "residential"), ("setapak", "path"), ("gang", "living_street"),
            ("lain", "residential"))

    def __init__(self, src, context):
        names = [f.name() for f in src.fields()]
        low = {n.lower(): n for n in names}
        f_cls = next((low[k] for k in ("highway", "fclass", "kelas", "remark", "fungsi") if k in low), None)
        f_nm = next((low[k] for k in ("name", "nama", "namobj", "nama_jalan") if k in low), None)
        f_ow = next((low[k] for k in ("oneway", "satu_arah") if k in low), None)
        tr = QgsCoordinateTransform(src.sourceCrs(), QgsCoordinateReferenceSystem("EPSG:4326"),
                                    context.transformContext())
        self.roads = []
        for f in src.getFeatures():
            g = f.geometry()
            if g is None or g.isEmpty():
                continue
            g = QgsGeometry(g)
            g.transform(tr)
            cls = self._cls(f[f_cls] if f_cls else None)
            if cls is None:
                continue
            nm = f[f_nm] if f_nm else None
            ow = str(f[f_ow]).strip().lower() in ("yes", "1", "-1", "f", "t", "true") if f_ow else False
            for p in _xy_parts(g):
                if len(p) >= 2:
                    lab = ("n:" + str(nm).strip().lower()) if nm not in (None, "") and str(nm) != "NULL" else \
                        ("w:%s" % f.id())
                    self.roads.append((p, cls, lab, ow))

    def _cls(self, v):
        s = "" if v is None or str(v) == "NULL" else str(v).strip().lower()
        if s in C.ROAD_TOL:
            return s
        for k, c in self.KEYS:
            if k in s:
                return c
        return "residential"

    def roads_in(self, boxes):
        bs = list(boxes)
        if not bs:
            return []
        x0 = min(b[0] for b in bs); y0 = min(b[1] for b in bs); x1 = max(b[2] for b in bs); y1 = max(b[3] for b in bs)
        return [r for r in self.roads if any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in r[0])]


_POST = []      # referensi post-processor agar tidak dibuang garbage collector sebelum dijalankan


class _Base(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    F_PRODUK = "FIELD_PRODUCT"
    NILAI = "PRODUCT_VALUES"
    F_TGL = "FIELD_DATE"
    PRIOR = "PRIORITY"
    DAYFIRST = "DAYFIRST"
    TOL = "TOLERANCE"
    COVER = "MIN_COVER"
    MODE = "MODE"
    F_GRUP = "FIELD_GROUP"
    EXPR = "EXTRA_FILTER"
    SNAP = "SNAP_TOLERANCE"
    GAP = "GAP_BRIDGE"
    SMART = "SMART_GAP"
    F_IDENT = "FIELD_CABLE_ID"
    FRAGMIN = "MIN_STRAND"
    DRIFT = "DRIFT_BAND"
    PROFILE = "DATA_PROFILE"
    MINPC = "MIN_PIECE"
    PERUNIT = "OUTPUT_UNIT"
    COPYATTR = "COPY_ATTRIBUTES"
    KABEL = "SINGLE_LINES"
    SHPDIR = "SHP_FOLDER"
    OUTPUT = "OUTPUT"
    SEGMEN = "SEGMENTS"
    CATATAN = "NOTES"
    REPORT = "REPORT"
    OPEN = "OPEN_REPORT"
    SKIPND = "SKIP_NO_DATE"
    ROADS = "ROAD_MATCHING"
    ROADLYR = "ROAD_LAYER"
    QC_ONLY = False

    def createInstance(self):
        return type(self)()

    def group(self):
        return ""

    def groupId(self):
        return ""

    def icon(self):
        return QIcon(os.path.join(HERE, "icon.png"))

    # ------------------------------------------------------------------ parameter
    def initAlgorithm(self, config=None):
        # Isian utama: layer garis + nilai produk/LOB. Sisanya di Advanced dengan nilai bawaan yang teruji.
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Line layer (cables/routes) to consolidate", [K.SRC_LINE]))
        self.addParameter(QgsProcessingParameterString(
            self.NILAI, "Product/LOB values to keep, comma-separated (empty = all lines)", "",
            optional=True))
        self.addParameter(K.advanced(QgsProcessingParameterField(
            self.F_PRODUK, "Product/LOB column (found automatically when left at the default)", "PRODUCT", self.INPUT,
            K.FIELD_ANY, False, True)))
        self.addParameter(K.advanced(QgsProcessingParameterField(
            self.F_TGL, "Creation-date column (found automatically when left at the default)", "CREATEDATE",
            self.INPUT, K.FIELD_ANY, False, True)))
        self.addParameter(K.advanced(QgsProcessingParameterBoolean(
            self.SKIPND, "Stop when the layer has no creation-date column (default: warn and keep the longest line)",
            False)))
        self.addParameter(K.advanced(QgsProcessingParameterEnum(self.PRIOR, "Line priority within a corridor",
                                                                PRIORITAS, defaultValue=0)))
        self.addParameter(K.advanced(QgsProcessingParameterNumber(
            self.TOL, "Corridor half-width (m): lines closer than this are one route (default 7.5 = 15 m corridor, "
            "right-of-way of a medium road; 2.5 = exact copies only)", K.NUM_DOUBLE, DEFAULT_TOL, False, 0.01, 1000.0)))
        self.addParameter(K.advanced(QgsProcessingParameterEnum(
            self.ROADS, "Road matching: lines on both sides of the same road become one line", ROAD_MODES,
            defaultValue=0)))
        self.addParameter(K.advanced(QgsProcessingParameterFeatureSource(
            self.ROADLYR, "Own road centreline layer (optional, replaces OpenStreetMap; class from a 'highway' or "
            "'fclass' field)", [K.SRC_LINE], optional=True)))
        self.addParameter(K.advanced(QgsProcessingParameterEnum(self.MODE, "Consolidation method", MODES,
                                                                defaultValue=0)))
        self.addParameter(K.advanced(QgsProcessingParameterField(
            self.F_GRUP, "Group column (optional): consolidate separately per value, e.g. route or cluster ID", None,
            self.INPUT, K.FIELD_ANY, False, True)))
        self.addParameter(K.advanced(QgsProcessingParameterField(
            self.F_IDENT, "Cable ID column (optional, e.g. NAME): gaps between pieces of the same cable may be joined",
            "NAME", self.INPUT, K.FIELD_ANY, False, True)))
        if not self.QC_ONLY:
            self.addParameter(K.advanced(QgsProcessingParameterNumber(
                self.SMART, "Join collinear gaps / gaps within the same cable up to (m, 0 = off)", K.NUM_DOUBLE, 10.0,
                False, 0.0, 1000.0)))
        self.addParameter(K.advanced(QgsProcessingParameterExpression(
            self.EXPR, "Extra filter (QGIS expression, optional)", None, self.INPUT, optional=True)))
        self.addParameter(K.advanced(QgsProcessingParameterNumber(
            self.FRAGMIN, "Strands shorter than this are marked FRAGMEN (m; default 25 = half a 50 m pole span)",
            K.NUM_DOUBLE, 25.0, False, 0.0, 100000.0)))
        self.addParameter(K.advanced(QgsProcessingParameterNumber(
            self.DRIFT, "Drift band (m, 0 = automatic 2 x tolerance): parallel lines inside it are the same corridor",
            K.NUM_DOUBLE, 0.0, False, 0.0, 1000.0)))
        self.addParameter(K.advanced(QgsProcessingParameterBoolean(
            self.PROFILE, "Compute the line-distance profile to assess the tolerance (report)", True)))
        self.addParameter(K.advanced(QgsProcessingParameterNumber(
            self.COVER, "Duplicate threshold: percent of a line's length inside another line's corridor", K.NUM_DOUBLE,
            80.0, False, 1.0, 100.0)))
        self.addParameter(K.advanced(QgsProcessingParameterBoolean(
            self.DAYFIRST, "Read dates like 03/05/2019 as day/month/year", True)))
        self.addParameter(K.advanced(QgsProcessingParameterNumber(
            self.SNAP, "End-point join tolerance (m, 0 = automatic: half the corridor tolerance, max. 1 m)",
            K.NUM_DOUBLE, 0.0, False, 0.0, 100.0)))
        self.addParameter(K.advanced(QgsProcessingParameterNumber(
            self.MINPC, "Minimum piece length (m, 0 = automatic: 2 x corridor tolerance, min. 1 m)",
            K.NUM_DOUBLE, 0.0, False, 0.0, 10000.0)))
        if not self.QC_ONLY:
            self.addParameter(K.advanced(QgsProcessingParameterNumber(
                self.GAP, "Bridge ALL gaps pointing to another strand up to (m, 0 = off)", K.NUM_DOUBLE,
                0.0, False, 0.0, 10000.0)))
            self.addParameter(K.advanced(QgsProcessingParameterEnum(
                self.PERUNIT, "Strand output form", KELUARAN, defaultValue=0)))
            self.addParameter(K.advanced(QgsProcessingParameterBoolean(
                self.COPYATTR, "Copy the attributes of the top-priority line to each strand", True)))
            self.addParameter(QgsProcessingParameterFeatureSink(
                self.KABEL, "Single lines: oldest line per corridor, no stacking, original attributes", K.SRC_LINE))
            self.addParameter(K.advanced(QgsProcessingParameterFeatureSink(
                self.OUTPUT, "Strands: connected network after merging", K.SRC_LINE)))
        seg = QgsProcessingParameterFeatureSink(
            self.SEGMEN, "Decision per input line (kept / trimmed / duplicate)", K.SRC_LINE,
            optional=self.QC_ONLY is False, createByDefault=True)
        self.addParameter(seg if self.QC_ONLY else K.advanced(seg))
        self.addParameter(K.advanced(QgsProcessingParameterFeatureSink(
            self.CATATAN, "Topology notes (ends, junctions, gaps, bridges)", K.SRC_POINT,
            optional=True, createByDefault=True)))
        self.addParameter(K.advanced(QgsProcessingParameterFileDestination(
            self.REPORT, "HTML report", "HTML (*.html)", optional=True, createByDefault=True)))
        if not self.QC_ONLY:
            self.addParameter(QgsProcessingParameterFolderDestination(
                self.SHPDIR, "Also save all results as Shapefiles (.shp) in this folder (optional)", optional=True,
                createByDefault=False))
        self.addParameter(K.advanced(QgsProcessingParameterBoolean(self.OPEN, "Open the report when finished", True)))
        for name, desc in (("N_KABEL", "Single lines (features)"), ("N_STRAND", "Strands"),
                           ("N_FRAGMEN", "Short strands (fragments)"), ("N_JEMBATAN", "Bridged gaps"),
                           ("N_INPUT", "Candidate lines"), ("N_DUPLIKAT", "Duplicate lines"),
                           ("PANJANG_AWAL_M", "Candidate length (m)"), ("PANJANG_AKHIR_M", "Strand length (m)")):
            self.addOutput(QgsProcessingOutputNumber(name, desc))
        for name, desc in (("N_CELAH", "Gaps to check"), ("N_CABANG", "Junctions"),
                           ("PANJANG_KABEL_M", "Single-line length (m)"), ("N_TGL_KOSONG", "Lines without a readable date")):
            self.addOutput(QgsProcessingOutputNumber(name, desc))
        for name, desc in (("TERTUA", "Oldest kept cable (name | date)"), ("KOLOM_TANGGAL", "Date column used"),
                           ("KOLOM_PRODUK", "Product column used"), ("DASAR_URUTAN", "Priority basis (date or length)"),
                           ("SHP_KABEL", "Single-line Shapefile")):
            self.addOutput(QgsProcessingOutputString(name, desc))

    # ------------------------------------------------------------------ proses
    def processAlgorithm(self, parameters, context, feedback):
        t0 = time.time()
        src = self.parameterAsSource(parameters, self.INPUT, context)
        if src is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        lyr_name = ""
        try:
            lyr = self.parameterAsVectorLayer(parameters, self.INPUT, context)
            lyr_name = lyr.name() if lyr else ""
        except Exception:
            pass
        lyr_name = lyr_name or src.sourceName()
        fields = src.fields()

        f_prod_in = (self.parameterAsFields(parameters, self.F_PRODUK, context) or [None])[0]
        f_tgl_in = (self.parameterAsFields(parameters, self.F_TGL, context) or [None])[0]
        f_grp_in = (self.parameterAsFields(parameters, self.F_GRUP, context) or [None])[0]
        f_id_in = (self.parameterAsFields(parameters, self.F_IDENT, context) or [None])[0]
        values = [v.strip() for v in (self.parameterAsString(parameters, self.NILAI, context) or "").split(",")
                  if v.strip()]
        f_prod = resolve_field(fields, f_prod_in)
        f_tgl = resolve_field(fields, f_tgl_in)
        f_grp = resolve_field(fields, f_grp_in)
        allnames = ", ".join(f.name() for f in fields)
        if f_prod is False and values:
            # kolom lini bisnis bisa bernama lain di data operator: PRODUCT / LOB / PRODUK
            for alt in [D.pick_product_field([f.name() for f in fields])] + list(PRODUCT_ALIASES):
                hit = resolve_field(fields, alt) if alt else None
                if hit:
                    feedback.pushInfo("Product column '%s' not found; using column '%s'." % (f_prod_in, hit))
                    f_prod = hit
                    break
        if f_prod is False and values:
            raise QgsProcessingException(
                "Product column '%s' is not in the layer. Choose the right column under Advanced, or leave the product "
                "values empty to keep all lines. Columns: %s" % (f_prod_in, allnames))
        if f_tgl is False:
            # kolom bawaan (CREATEDATE) tidak ada: cari otomatis dari nama, tipe, dan isi kolom
            smp = {f.name(): [] for f in fields}
            req0 = QgsFeatureRequest()
            req0.setLimit(300)
            try:
                for ft in src.getFeatures(req0):
                    for f in fields:
                        smp[f.name()].append(ft[f.name()])
            except Exception:
                pass
            hit, why_d = D.pick_date_field([(f.name(), f.typeName()) for f in fields], smp)
            if hit:
                feedback.pushInfo("Date column '%s' not found; using column '%s' automatically (%s)." % (f_tgl_in, hit,
                                                                                                        why_d))
                f_tgl = hit
        skip_nd = self.parameterAsBool(parameters, self.SKIPND, context)
        if f_tgl is False or not f_tgl:
            # Tidak ada kolom tanggal pembuatan: garis bertumpuk tetap dijadikan satu, tetapi urutan umur TIDAK bisa
            # diterapkan -> garis terpanjang dipertahankan, ditandai jelas (su_dasar = PANJANG, nama berkas
            # ..._TANPA_TANGGAL). Nomor ID (mis. LINK1) sengaja tidak dipakai sebagai pengganti tanggal.
            msg_nd = ("NO CREATION-DATE COLUMN in '%s' (columns: %s). Stacked lines are still reduced to one line per "
                      "corridor, but the oldest line CANNOT be determined: the longest line is kept instead and every "
                      "result is marked su_dasar = PANJANG / file name ..._%s." % (lyr_name, allnames, NODATE_TAG))
            if skip_nd:
                raise QgsProcessingException(msg_nd.replace("Stacked lines are still", "Skipped (option 'Stop when "
                                                            "the layer has no creation-date column'); stacked lines "
                                                            "would be") + " ")
            feedback.pushWarning(msg_nd)
            f_tgl = None
        if f_grp is False:
            raise QgsProcessingException("Group column '%s' is not in the layer. Columns: %s" % (f_grp_in, allnames))
        f_id = resolve_field(fields, f_id_in)
        if f_id is False:
            feedback.pushInfo("Cable ID column '%s' not in the layer; gaps are only joined when collinear." % f_id_in)
            f_id = None
        if f_prod is False:
            f_prod = None
        if not values:
            f_prod_filter = None
        else:
            f_prod_filter = f_prod
        newest = self.parameterAsEnum(parameters, self.PRIOR, context) == 1
        dayfirst = self.parameterAsBool(parameters, self.DAYFIRST, context)
        tol = self.parameterAsDouble(parameters, self.TOL, context)
        cover = self.parameterAsDouble(parameters, self.COVER, context) / 100.0
        mode = self.parameterAsEnum(parameters, self.MODE, context)
        snap = self.parameterAsDouble(parameters, self.SNAP, context) or None
        minpc = self.parameterAsDouble(parameters, self.MINPC, context) or None
        expr_s = self.parameterAsExpression(parameters, self.EXPR, context)
        gap = 0.0 if self.QC_ONLY else self.parameterAsDouble(parameters, self.GAP, context)
        smart = 0.0 if self.QC_ONLY else self.parameterAsDouble(parameters, self.SMART, context)
        frag_min = self.parameterAsDouble(parameters, self.FRAGMIN, context)
        drift = self.parameterAsDouble(parameters, self.DRIFT, context) or None
        do_profile = self.parameterAsBool(parameters, self.PROFILE, context)
        per_unit = 0 if self.QC_ONLY else self.parameterAsEnum(parameters, self.PERUNIT, context)
        copyattr = False if self.QC_ONLY else self.parameterAsBool(parameters, self.COPYATTR, context)

        # ---- CRS kerja dalam meter, dengan distorsi skala kecil
        src_crs = src.sourceCrs()
        if not src_crs.isValid():
            raise QgsProcessingException("The layer has no valid CRS. Set the layer CRS first.")
        da = QgsDistanceArea()
        da.setSourceCrs(src_crs, context.transformContext())
        da.setEllipsoid(src_crs.ellipsoidAcronym() or "EPSG:7030")
        # CRS hitung: zona UTM per kelompok ruang (lihat bawah). Hasil tidak bergantung pada CRS layer maupun luas
        # wilayah yang diproses: kelompok yang sama selalu dihitung di zona yang sama.
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        src_to_wgs = QgsCoordinateTransform(src_crs, wgs84, context.transformContext())
        kscale, why = None, ""

        # ---- baca & filter
        req = QgsFeatureRequest()
        if expr_s:
            ex = QgsExpression(expr_s)
            if ex.hasParserError():
                raise QgsProcessingException("Invalid filter expression: %s" % ex.parserErrorString())
            ectx = self.createExpressionContext(parameters, context, src)
            req.setFilterExpression(expr_s)
            req.setExpressionContext(ectx)
        want = set(v.upper() for v in values)
        total = src.featureCount() if src.featureCount() >= 0 else 0
        records, feats, ident, pending = [], {}, {}, []
        n_read = n_out_prod = n_out_expr = n_bad_date = n_nogeom = 0
        prod_seen = {}
        for i, f in enumerate(src.getFeatures(req)):
            if feedback.isCanceled():
                return {}
            n_read += 1
            if f_prod_filter:
                pv = f[f_prod_filter]
                pvs = "" if pv is None or str(pv).upper() == "NULL" else str(pv).strip()
                prod_seen[pvs] = prod_seen.get(pvs, 0) + 1
                if pvs.upper() not in want:
                    n_out_prod += 1
                    continue
            g = f.geometry()
            if g is None or g.isNull() or g.isEmpty():
                n_nogeom += 1
                box = None
            else:
                try:
                    bb = src_to_wgs.transformBoundingBox(g.boundingBox())
                    box = (bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum())
                except Exception:
                    box = None
            d = None
            if f_tgl:
                d = C.parse_date(f[f_tgl], dayfirst)
                if d is None:
                    n_bad_date += 1
            grp = None
            if f_grp:
                gv = f[f_grp]
                grp = None if gv is None or str(gv) == "NULL" else str(gv)
            if f_id:
                iv = f[f_id]
                ident[f.id()] = None if iv is None or str(iv) in ("", "NULL") else str(iv).strip()
            pending.append((f.id(), d, grp, box))
            feats[f.id()] = f
            if total and i % 500 == 0:
                feedback.setProgress(min(30.0, 30.0 * i / total))
        # ---- kelompok ruang + zona UTM per kelompok
        reach = max(gap, smart, 10.0 * max(tol, 1.0), (drift or 2.0 * tol), tol, snap or 0.0) + 5.0
        boxes = {}
        for fid_, d_, g_, box in pending:
            if box is None:
                continue
            lat = min(max(abs(box[1]), abs(box[3])), 85.0)
            px = reach / (111320.0 * math.cos(math.radians(lat)))
            py = reach / 110574.0
            boxes[fid_] = (box[0] - px, box[1] - py, box[2] + px, box[3] + py)
        clusters = C.spatial_clusters(boxes, 0.0, 0.0)
        zone_of, slots = {}, {}
        for cl in clusters:
            x0 = min(boxes[k][0] for k in cl); x1 = max(boxes[k][2] for k in cl)
            y0 = min(boxes[k][1] for k in cl); y1 = max(boxes[k][3] for k in cl)
            z = utm_for((x0 + x1) / 2.0, (y0 + y1) / 2.0)
            code = int(z.authid().split(":")[1])
            if code not in slots:
                slots[code] = (z, QgsCoordinateTransform(src_crs, z, context.transformContext()),
                               QgsCoordinateTransform(z, src_crs, context.transformContext()),
                               QgsCoordinateTransform(z, wgs84, context.transformContext()))
            for k in cl:
                zone_of[k] = code
        rec_of = {}
        for fid_, d_, grp_, box in pending:
            code = zone_of.get(fid_)
            parts = []
            if code is not None:
                g = QgsGeometry(feats[fid_].geometry())
                g.transform(slots[code][1])
                off = slot_offset(code)
                parts = [[(x + off, y) for x, y in p] for p in _xy_parts(g)]
            rec = C.Record(fid_, parts, d_, grp_, newest, uid=_attr_uid(feats[fid_]))
            records.append(rec)
            rec_of[fid_] = rec
        del pending
        work_crs_txt = ", ".join("%s (%d kelompok)" % (slots[c][0].authid(), sum(1 for cl in clusters
                                                                                  if zone_of[cl[0]] == c))
                                 for c in sorted(slots)) or "-"
        feedback.pushInfo("Computed in the UTM zone of each spatial group: %s. %d independent groups (interaction "
                          "reach %s m); each group's result does not depend on the extent processed."
                          % (work_crs_txt, len(clusters), C._id(reach, 0)))

        if expr_s:
            try:
                n_out_expr = max(0, total - n_read)
            except Exception:
                n_out_expr = 0
        feedback.pushInfo("Read %d lines; %d pass the filter (removed by product %d, by expression %d)." % (
            n_read, len(records), n_out_prod, n_out_expr))
        if not records:
            seen = ", ".join("%s (%d)" % (k or "<kosong>", v) for k, v in sorted(prod_seen.items(),
                                                                                  key=lambda kv: -kv[1])[:12])
            raise QgsProcessingException(
                "No lines match %s. Product values in the data: %s" % (
                    ("%s = %s" % (f_prod_filter, ", ".join(values))) if f_prod_filter else "filter",
                    seen or "-"))
        nodate = f_tgl is None
        if f_tgl and n_bad_date >= len(records):
            nodate = True
            feedback.pushWarning("Column '%s' has no readable creation date in any selected line: the longest line "
                                 "is kept per corridor instead (marked su_dasar = PANJANG)." % f_tgl)
        elif n_bad_date:
            feedback.pushWarning("%d lines have an empty or unreadable creation date -> placed last in priority "
                                 "(never treated as the oldest)." % n_bad_date)

        # ---- inti
        feedback.setProgressText("Selecting one line per corridor and building strands...")
        cl_recs = [[rec_of[k] for k in cl] for cl in clusters]
        loose = [r for r in records if r.fid not in zone_of]
        if loose:
            cl_recs.append(loose)
        # ---- jalan acuan (OpenStreetMap otomatis atau layer jalan sendiri)
        road_mode = self.parameterAsEnum(parameters, self.ROADS, context)
        road_src_lyr = self.parameterAsSource(parameters, self.ROADLYR, context)
        road_info = {"mode": "off", "source": "", "n_roads": 0, "note": ""}
        road_source = None
        if mode != C.MODE_SEMUA and (road_src_lyr is not None or road_mode == 0):
            feedback.setProgressText("Loading road centrelines...")
            try:
                if road_src_lyr is not None:
                    road_source = _LayerRoads(road_src_lyr, context)
                    road_info.update(mode="layer", source=road_src_lyr.sourceName())
                else:
                    from . import roads as RD
                    road_source = RD.RoadSource([boxes[k] for k in boxes], feedback)
                    road_info.update(mode="osm", source=road_source.mode, note=road_source.note)
            except Exception as e:
                road_source = None
                road_info.update(mode="failed", note=str(e))
                feedback.pushWarning("Road matching skipped (%s). Lines are consolidated with the distance corridor "
                                     "only." % e)
        parts_res = []
        for ci_, rs in enumerate(cl_recs):
            if feedback.isCanceled():
                return {}
            roads_ci = None
            code = zone_of.get(rs[0].fid) if rs else None
            if road_source is not None and code is not None:
                try:
                    raw = road_source.roads_in([boxes[r.fid] for r in rs if r.fid in boxes])
                    trw = QgsCoordinateTransform(wgs84, slots[code][0], context.transformContext())
                    off = slot_offset(code)

                    def _gen(raw=raw, trw=trw, off=off):
                        for pts, hw, lab, ow in raw:
                            g = QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in pts])
                            g.transform(trw)
                            yield [(p.x() + off, p.y()) for p in g.asPolyline()], hw, lab, ow
                    # hanya ruas jalan di sekitar garis kabel yang disimpan (hemat memori)
                    roads_ci = C.RoadMatcher(_gen(), near_cells=C._near_cells(rs, 25.0))
                    raw = None
                    road_info["n_roads"] += roads_ci.n_labels
                except Exception as e:
                    roads_ci = None
                    road_info["note"] = str(e)
                    feedback.pushWarning("Road centrelines could not be loaded for group %d: %s" % (ci_ + 1, e))
            parts_res.append(C.consolidate(rs, tol=tol, min_cover=cover, mode=mode, snap_tol=snap, gap_tol=gap,
                                           min_piece=minpc, smart_tol=smart, ident=ident or None, drift=drift,
                                           roads=roads_ci))
            roads_ci = None
            feedback.setProgress(30.0 + 35.0 * (ci_ + 1) / len(cl_recs))
        if road_source is not None and getattr(road_source, "note", "") and not road_info["note"]:
            road_info["note"] = road_source.note
        res = C.merge_results(parts_res)
        del parts_res, cl_recs
        feedback.setProgress(65)
        profile = None
        if do_profile:
            feedback.setProgressText("Computing the line-distance profile...")
            try:
                profile = C.separation_profile(records, max_d=max(10.0, math.ceil(2.0 * tol + 5.0)))
            except Exception as e:
                feedback.pushWarning("Distance profile could not be computed: %r" % e)
        feedback.setProgress(70)
        # panjang elipsoidal (meter sebenarnya di permukaan bumi) per garis masukan
        len_e = {}
        for r in records:
            try:
                len_e[r.fid] = da.measureLength(feats[r.fid].geometry()) if r.length > 0 else 0.0
            except Exception:
                len_e[r.fid] = r.length
        for r in records:
            r.len_e = len_e.get(r.fid, r.length)
            r.kept_e = r.kept_len * (r.len_e / r.length) if r.length > 0 else 0.0
        rec_by = {r.fid: r for r in res["order"]}

        # ---- untai
        strands = []        # dict: id, grp, lines(work), summary
        sid_of_fid = {}
        n = 0
        for grp, g in res["groups"].items():
            for comp in g["comps"]:
                summ = C.strand_summary(g["chains"], comp)
                if per_unit == 1:
                    units = [[g["chains"][c][0]] for c in comp]
                else:
                    units = [summ["lines"]]
                for u_i, lines in enumerate(units):
                    n += 1
                    sid = "S%03d" % n
                    owners = summ["owners"] if per_unit == 0 else (
                        C._ow(g["chains"][comp[u_i]][1]) - {"JEMBATAN"})
                    strands.append({"id": sid, "grp": grp, "lines": lines, "summ": summ, "owners": owners})
                    for o in owners:
                        sid_of_fid.setdefault(o, sid)
        bridges_total = sum(sum(b[0] for b in g["bridges"]) for g in res["groups"].values())
        # indeks spasial untai per grup -> untai mana yang memuat sebuah titik (ujung, celah, jembatan)
        sidx = {}
        for s_ in strands:
            ix = sidx.setdefault(s_["grp"], C.SegIndex(25.0))
            for li, ln in enumerate(s_["lines"]):
                ix.add_line(s_["id"], li, ln)

        def sid_at(grp, p, r=0.05):
            ix = sidx.get(grp)
            hit = ix.nearest(p, r) if ix is not None else None
            return ix.segs[hit[1]][0] if hit else ""
        bridge_m = {}
        for grp, g in res["groups"].items():
            for br in g["bridges"]:
                k_ = sid_at(grp, br[1])
                bridge_m[k_] = bridge_m.get(k_, 0.0) + br[0]

        def back(pts):
            out_ = []
            for x, y in pts:
                code = slot_of(x)
                p_ = slots[code][2].transform(QgsPointXY(x - slot_offset(code), y))
                out_.append((p_.x(), p_.y()))
            return out_

        # ---- ringkasan per untai (dipakai keluaran dan laporan)
        for s in strands:
            owners = sorted((o for o in s["owners"] if o in rec_by), key=lambda o: rec_by[o].rank)
            dates = [rec_by[o].date for o in owners if rec_by[o].date is not None]
            prods = []
            if f_prod:
                for o in owners:
                    v = feats[o][f_prod]
                    v = "" if v is None or str(v) == "NULL" else str(v)
                    if v and v not in prods:
                        prods.append(v)
            geom = _mline([back(pp) for pp in s["lines"]])
            try:
                length = da.measureLength(geom)          # meter elipsoidal
            except Exception:
                length = 0.0
            if not length:
                length = sum(C.line_len(pp) for pp in s["lines"])
            summ = s["summ"]
            if len(s["lines"]) == 1:
                deg_ends, deg_j = (0 if summ["closed"] else 2), 0
            else:
                sub = C.node_degrees([(pp, None) for pp in s["lines"]])
                deg_ends = sum(1 for v in sub.values() if v == 1)
                deg_j = sum(1 for v in sub.values() if v >= 3)
            s.update({"geom": geom, "length": length, "owners_sorted": owners, "n_ujung": deg_ends,
                      "n_cabang": deg_j, "utuh": len(s["lines"]) == 1, "date_min": min(dates) if dates else None,
                      "date_max": max(dates) if dates else None, "prods": prods,
                      "kelas": "FRAGMEN" if length < frag_min else "UTAMA",
                      "jembatan": bridge_m.get(s["id"], 0.0)})

        out = {}
        dest_strand = None
        shp_jobs = {}           # nama -> (akhiran, fields, wkb, [fitur]) untuk ekspor Shapefile opsional
        if not self.QC_ONLY:
            sf = QgsFields()
            spec = (("strand_id", K.T_STR, 12), ("kelas", K.T_STR, 10), ("grup", K.T_STR, 80),
                    ("panjang_m", K.T_DBL, 0), ("n_garis", K.T_INT, 0), ("fid_sumber", K.T_STR, 254),
                    ("n_ruas", K.T_INT, 0), ("n_ujung", K.T_INT, 0), ("n_cabang", K.T_INT, 0), ("utuh", K.T_STR, 5),
                    ("tgl_tertua", K.T_STR, 20), ("tgl_baru", K.T_STR, 20), ("produk", K.T_STR, 80),
                    ("jembatan_m", K.T_DBL, 0), ("fid_utama", K.T_STR, 20))
            for nm, tp, ln in spec:
                sf.append(K.field(nm, tp, ln))
            copied = []
            if copyattr:
                low = set(x[0].lower() for x in spec)
                for fd in fields:
                    nm = fd.name()
                    new = nm if nm.lower() not in low else nm + "_src"
                    fcopy = QgsField(fd)
                    fcopy.setName(new)
                    sf.append(fcopy)
                    copied.append(nm)
                    low.add(new.lower())
            sink, dest_strand = self.parameterAsSink(parameters, self.OUTPUT, context, sf, K.WKB_MLINE, src_crs)
            shp_jobs["untai"] = ("untai", sf, K.WKB_MLINE, [])
            if sink is None:
                raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
            for s in strands:
                owners = s["owners_sorted"]
                ft = QgsFeature(sf)
                ft.setGeometry(s["geom"])
                vals = [s["id"], s["kelas"], s["grp"] or "", round(s["length"], 3), len(owners), _short_list(owners),
                        len(s["lines"]), s["n_ujung"], s["n_cabang"], "YA" if s["utuh"] else "TIDAK",
                        _fmt_date(s["date_min"]), _fmt_date(s["date_max"]), ", ".join(s["prods"])[:80],
                        round(s["jembatan"], 3), str(owners[0]) if owners else ""]
                if copyattr:
                    top = feats[owners[0]] if owners else None
                    vals += [top[nm] if top is not None else None for nm in copied]
                ft.setAttributes(vals)
                sink.addFeature(ft, K.FAST)
                shp_jobs["untai"][3].append(ft)
            out[self.OUTPUT] = dest_strand
        feedback.setProgress(80)

        # ---- dasar urutan per garis: TANGGAL (tanggal pembuatan terbaca) atau PANJANG (tanpa tanggal -> terpanjang)
        def basis(r):
            return "TANGGAL" if r.date is not None else "PANJANG"

        # ---- keputusan per garis
        segf = QgsFields()
        for fd in fields:
            segf.append(fd)
        extra = (("su_status", K.T_STR, 20), ("su_alasan", K.T_STR, 254), ("su_urutan", K.T_INT, 0),
                 ("su_tanggal", K.T_STR, 20), ("su_tgl_ok", K.T_STR, 5), ("su_panjang", K.T_DBL, 0),
                 ("su_dipakai", K.T_DBL, 0), ("su_cakupan", K.T_DBL, 0), ("su_dup_fid", K.T_STR, 20),
                 ("su_strand", K.T_STR, 12), ("su_fid", K.T_STR, 20), ("su_dasar", K.T_STR, 10))
        existing = set(f.name().lower() for f in fields)
        for nm, tp, ln in extra:
            if nm.lower() in existing:
                raise QgsProcessingException("The layer already has a column %s (a previous Seuntai result?). Use the "
                                             "original layer as input." % nm)
            segf.append(K.field(nm, tp, ln))
        seg_sink, dest_seg = self.parameterAsSink(parameters, self.SEGMEN, context, segf, K.WKB_MLINE, src_crs)
        shp_jobs["keputusan"] = ("keputusan", segf, K.WKB_MLINE, [])
        seg_geom = {}
        for r in res["order"]:
            f = feats[r.fid]
            ft = QgsFeature(segf)
            g = f.geometry()
            if g is not None and not g.isNull():
                g = QgsGeometry(g)
                try:
                    if QgsWkbTypes.isCurvedType(g.wkbType()):
                        g.convertToStraightSegment()
                    g = QgsGeometry.fromMultiPolylineXY(g.asMultiPolyline() if g.isMultipart() else [g.asPolyline()])
                except Exception:
                    g = QgsGeometry()
                ft.setGeometry(g)
                seg_geom[r.fid] = g
            ft.setAttributes(list(f.attributes()) + [
                r.status, r.note[:254], r.rank, _fmt_date(r.date), "YA" if r.date is not None or not f_tgl else "TIDAK",
                round(r.len_e, 3), round(r.kept_e, 3), round(r.cover * 100.0, 1),
                "" if r.dup_of is None else str(r.dup_of), sid_of_fid.get(r.fid, ""), str(r.fid), basis(r)])
            if seg_sink is not None:
                seg_sink.addFeature(ft, K.FAST)
            shp_jobs["keputusan"][3].append(ft)
        if seg_sink is not None:
            out[self.SEGMEN] = dest_seg

        # ---- kabel tunggal: garis tertua per koridor dengan atribut aslinya (tanpa tumpukan)
        n_kabel = 0
        kabel_rows = []
        if not self.QC_ONLY:
            kf = QgsFields()
            for fd in fields:
                kf.append(fd)
            for nm, tp, ln in (("su_status", K.T_STR, 20), ("su_tanggal", K.T_STR, 20), ("su_urutan", K.T_INT, 0),
                               ("su_panjang", K.T_DBL, 0), ("su_dipakai", K.T_DBL, 0), ("su_strand", K.T_STR, 12),
                               ("su_fid", K.T_STR, 20), ("su_dasar", K.T_STR, 10)):
                kf.append(K.field(nm, tp, ln))
            k_sink, dest_k = self.parameterAsSink(parameters, self.KABEL, context, kf, K.WKB_MLINE, src_crs)
            shp_jobs["kabel"] = ("kabel_tunggal", kf, K.WKB_MLINE, [])
            for r in res["order"]:          # urut prioritas: tertua lebih dulu
                if r.status not in (C.DIPAKAI, C.DIPANGKAS) or not r.pieces:
                    continue
                f = feats[r.fid]
                if r.status == C.DIPAKAI:
                    g = QgsGeometry(seg_geom.get(r.fid) or QgsGeometry())
                else:
                    g = _mline([back(pp[0]) for pp in r.pieces])
                if g is None or g.isNull():
                    continue
                ft = QgsFeature(kf)
                ft.setGeometry(g)
                ft.setAttributes(list(f.attributes()) + [r.status, _fmt_date(r.date), r.rank, round(r.len_e, 3),
                                                         round(r.kept_e, 3), sid_of_fid.get(r.fid, ""), str(r.fid),
                                                         basis(r)])
                if k_sink is not None:
                    k_sink.addFeature(ft, K.FAST)
                shp_jobs["kabel"][3].append(ft)
                kabel_rows.append(r)
                n_kabel += 1
            if k_sink is not None:
                out[self.KABEL] = dest_k

        # ---- catatan topologi
        def gap_text(gp, prefix):
            d, p_, q_, ga, gb, kind, same = gp
            t = "%s %s m ke untai %s" % (prefix + (" segaris" if kind == "SEGARIS" else " T"), C._id(d, 2),
                                         sid_at(grp, q_) or "?")
            if same is True:
                t += ", kabel sama"
            return t

        notes = []
        for grp, g in res["groups"].items():
            deg = C.node_degrees(g["chains"])
            seen = set()
            for ci, (pts, _o) in enumerate(g["chains"]):
                for p in (pts[0], pts[-1]):
                    kk = C._key(p)
                    if kk in seen:
                        continue
                    seen.add(kk)
                    dg = deg.get(kk, 0)
                    if dg == 1:
                        notes.append(("UJUNG", p, sid_at(grp, p), grp, None, "ujung bebas untai"))
                    elif dg >= 3:
                        notes.append(("CABANG", p, sid_at(grp, p), grp, None,
                                      "percabangan %d arah" % dg))
            done = []
            for br in g["bridges"]:
                notes.append(("JEMBATAN", br[1], sid_at(grp, br[1]), grp, br[0], gap_text(br, "celah")
                              + " (dijembatani)"))
                done.append(br)
            for gp in g["gaps"]:
                p, q = gp[1], gp[2]
                if any(min(C.seg_len(b[1], p), C.seg_len(b[2], p), C.seg_len(b[1], q)) < 1e-6 for b in done):
                    continue
                sa, sb = sid_at(grp, p), sid_at(grp, q)
                if sa and sa == sb and g["bridges"]:
                    continue        # sudah tersambung lewat jembatan lain
                notes.append(("CELAH", p, sa, grp, gp[0], gap_text(gp, "celah")))
        nf = QgsFields()
        for nm, tp, ln in (("jenis", K.T_STR, 12), ("strand_id", K.T_STR, 12), ("grup", K.T_STR, 80),
                           ("jarak_m", K.T_DBL, 0), ("keterangan", K.T_STR, 120)):
            nf.append(K.field(nm, tp, ln))
        note_sink, dest_note = self.parameterAsSink(parameters, self.CATATAN, context, nf, K.WKB_POINT, src_crs)
        shp_jobs["catatan"] = ("catatan", nf, K.WKB_POINT, [])
        for jenis, p, sid, grp, d, ket in notes:
            ft = QgsFeature(nf)
            x, y = back([p])[0]
            ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            ft.setAttributes([jenis, sid, grp or "", None if d is None else round(d, 3), ket])
            if note_sink is not None:
                note_sink.addFeature(ft, K.FAST)
            shp_jobs["catatan"][3].append(ft)
        if note_sink is not None:
            out[self.CATATAN] = dest_note

        # ---- ekspor Shapefile opsional (nama kolom sudah <= 10 karakter, batas format DBF)
        shp_dir = "" if self.QC_ONLY else self.parameterAsString(parameters, self.SHPDIR, context)
        shp_written = []
        shp_kabel = ""
        if shp_dir:
            # nama berkas: <layer>_<produk>[_TANPA_TANGGAL]_<jenis>.shp (produk & status tanggal terlihat dari nama)
            tag = lyr_name + ("_" + "_".join(values) if values else "") + ("_" + NODATE_TAG if nodate else "")
            base = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in tag)[:60].strip("_") or "seuntai"
            try:
                os.makedirs(shp_dir, exist_ok=True)
                for key in ("kabel", "untai", "keputusan", "catatan"):
                    if key not in shp_jobs:
                        continue
                    suffix, flds, wkb, fts = shp_jobs[key]
                    path = os.path.join(shp_dir, "%s_%s.shp" % (base, suffix))
                    write_shp(path, flds, wkb, src_crs, fts, context)
                    shp_written.append(path)
                    if key == "kabel":
                        shp_kabel = path
                feedback.pushInfo("Shapefiles written to %s: %s" % (shp_dir, ", ".join(os.path.basename(x)
                                                                                     for x in shp_written)))
            except Exception as e:
                feedback.reportError("Shapefiles could not be written to %s: %s" % (shp_dir, e))
        shp_jobs.clear()
        feedback.setProgress(90)

        # ---- ringkasan
        cnt = {}
        for r in res["order"]:
            cnt[r.status] = cnt.get(r.status, 0) + 1
        len_in = sum(r.len_e for r in res["order"])
        len_out = sum(s["length"] for s in strands)
        frags = [s for s in strands if s["kelas"] == "FRAGMEN"]
        n_bridge = sum(len(g["bridges"]) for g in res["groups"].values())
        checks = tolerance_checks(tol, profile)
        for lvl, msg in tolerance_checks(tol, profile, en=True):
            (feedback.pushWarning if lvl == "W" else feedback.pushInfo)(msg)
        stats = {"n_read": n_read, "n_cand": len(records), "n_out_prod": n_out_prod, "n_out_expr": n_out_expr,
                 "n_bad_date": n_bad_date, "n_nogeom": n_nogeom, "cnt": cnt, "len_in": len_in, "len_out": len_out,
                 "n_strand": len(strands), "n_frag": len(frags), "len_frag": sum(s["length"] for s in frags),
                 "n_bridge": n_bridge, "bridges_m": bridges_total,
                 "n_gap": sum(1 for nn in notes if nn[0] == "CELAH"),
                 "n_branch": sum(1 for nn in notes if nn[0] == "CABANG"),
                 "elapsed": time.time() - t0, "prod_seen": prod_seen, "profile": profile, "checks": checks,
                 "kscale": kscale, "crs_why": why, "n_kabel": n_kabel, "shp": shp_written,
                 "road": dict(road_info, merged_m=sum(getattr(r, "road_len", 0.0) for r in res["order"]),
                              n_lines=sum(1 for r in res["order"] if getattr(r, "road_len", 0.0) > 0)),
                 "oldest": oldest_rows(kabel_rows or [r for r in res["order"] if r.status in (C.DIPAKAI,
                                                                                              C.DIPANGKAS)],
                                       feats, f_id, f_prod, sid_of_fid)}
        rd = stats["road"]
        if rd["mode"] in ("osm", "layer") and not rd["n_roads"]:
            feedback.pushWarning("Road matching: no road centrelines were loaded near the lines (%s); only the "
                                 "distance corridor was used." % (rd.get("note") or "-"))
        if rd["mode"] in ("osm", "layer"):
            feedback.pushInfo("Road matching (%s, %d road centrelines): %.1f km of %d lines treated as the same route as "
                              "a line on the other side of the same road." % (
                                  rd["source"], rd["n_roads"], rd["merged_m"] / 1000.0, rd["n_lines"]))
        feedback.pushInfo("Result: %d strands (%d fragments < %s m), %d bridges, length %.1f m from %.1f m of "
                          "candidates. Status: %s" % (len(strands), len(frags), C._id(frag_min, 0), n_bridge, len_out, len_in,
                                          ", ".join("%s %d" % kv for kv in sorted(cnt.items()))))

        rpt = self.parameterAsFileOutput(parameters, self.REPORT, context)
        if rpt:
            try:
                meta = {"layer": lyr_name, "crs": src_crs.authid(), "work_crs": "UTM per kelompok ruang: " + work_crs_txt,
                        "f_prod": f_prod_filter or "", "values": values, "f_tgl": f_tgl or "", "f_grp": f_grp or "",
                        "expr": expr_s or "", "tol": tol, "cover": cover * 100, "mode": MODES_ID[mode],
                        "prior": ("Garis terpanjang dulu (tanpa tanggal pembuatan)" if nodate
                                  else PRIORITAS_ID[1 if newest else 0]), "nodate": nodate,
                        "snap": res["params"]["snap_tol"], "gap": gap,
                        "gap_report": res["params"]["gap_report"], "dayfirst": dayfirst, "qc_only": self.QC_ONLY,
                        "smart": smart, "f_id": f_id or "", "frag_min": frag_min, "drift": res["params"]["drift"],
                        "version": __version__, "author": __author__, "alg": self.displayName(),
                        "run": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "keluaran": KELUARAN_ID[per_unit] if not self.QC_ONLY else "-",
                        "road_mode": ROAD_MODES_ID[0] if road_info["mode"] in ("osm", "failed") else
                        ("Layer jalan sendiri: %s" % road_info["source"] if road_info["mode"] == "layer" else
                         ROAD_MODES_ID[1])}

                def wgs(pts):
                    o = []
                    for x, y in pts:
                        code = slot_of(x)
                        p = slots[code][3].transform(QgsPointXY(x - slot_offset(code), y))
                        o.append((round(p.x(), 7), round(p.y(), 7)))
                    return o
                report.build(rpt, meta, stats, res, strands, notes, wgs, feats, f_prod, rec_by)
                out[self.REPORT] = rpt
                self._report = rpt if self.parameterAsBool(parameters, self.OPEN, context) else None
            except Exception as e:      # laporan tidak boleh menggagalkan hasil utama
                feedback.reportError("HTML report could not be created: %r" % e)
                import traceback
                feedback.pushDebugInfo(traceback.format_exc())
        # gaya layer keluaran
        for key, kind in ((self.KABEL, "kabel"), (self.OUTPUT, "strand"), (self.SEGMEN, "segmen"),
                          (self.CATATAN, "catatan")):
            dest = out.get(key)
            if dest and context.willLoadLayerOnCompletion(dest):
                pp = styles.PostProcessor(kind)
                _POST.append(pp)
                context.layerToLoadOnCompletionDetails(dest).setPostProcessor(pp)
        old1 = stats["oldest"][0] if stats["oldest"] else None
        out.update({"N_CELAH": stats["n_gap"], "N_CABANG": stats["n_branch"],
                    "PANJANG_KABEL_M": round(sum(r.kept_e for r in kabel_rows), 3),
                    "TERTUA": ("%s | %s" % (old1["nama"] or ("FID %s" % old1["fid"]), old1["tanggal"])) if old1 else "",
                    "KOLOM_TANGGAL": f_tgl or "", "KOLOM_PRODUK": (f_prod_filter or ""),
                    "DASAR_URUTAN": "PANJANG" if nodate else "TANGGAL", "SHP_KABEL": shp_kabel,
                    "N_TGL_KOSONG": n_bad_date if f_tgl else len(records)})
        out.update({"N_KABEL": n_kabel, "N_STRAND": len(strands), "N_FRAGMEN": len(frags), "N_JEMBATAN": n_bridge,
                    "N_INPUT": len(records), "N_DUPLIKAT": cnt.get(C.DUPLIKAT, 0),
                    "PANJANG_AWAL_M": round(len_in, 3), "PANJANG_AKHIR_M": round(len_out, 3)})
        feedback.setProgress(100)
        return out

    def postProcessAlgorithm(self, context, feedback):
        rpt = getattr(self, "_report", None)
        if rpt and os.path.exists(rpt):
            try:
                from qgis.PyQt.QtCore import QUrl
                from qgis.PyQt.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl.fromLocalFile(rpt))
            except Exception:
                pass
        return {}


class KonsolidasiStrand(_Base):
    def name(self):
        return "konsolidasi_strand"

    def displayName(self):
        return "Consolidate One Layer"

    def shortDescription(self):
        return "Stacked or parallel lines in one corridor -> one line, the oldest by creation date, with its attributes."

    def shortHelpString(self):
        return (
            "<p><b>How to use</b>: pick the line layer, type the product/LOB values to keep (e.g. FTTT; empty = all "
            "lines) and click <b>Run</b>. Tip: <b>Vector &rsaquo; Seuntai &rsaquo; Consolidate Lines</b> lets you "
            "tick the product values from a list.</p>"
            "<p><b>What it does</b>: in every corridor where lines are stacked or run side by side, only the line "
            "with the <b>oldest creation date</b> is kept, with all its original attributes; the parallel parts of "
            "newer lines are removed and their unique parts are kept and joined. Lines with an empty or unreadable "
            "date are always last. If the layer has <b>no creation-date column</b>, a warning is shown and the "
            "longest line is kept instead (marked <code>su_dasar = PANJANG</code>).</p>"
            "<p><b>Output</b>: <b>Single lines</b> (one layer, no stacking) and, when a folder is given, Shapefiles "
            "named <code>&lt;layer&gt;_&lt;product&gt;_kabel_tunggal.shp</code>. <b>Advanced</b> holds the "
            "corridor half-width (7.5 m = 15 m corridor, drift band 15 m), the date and product columns, strands, "
            "decisions, topology notes and "
            "the HTML report (in Indonesian). Original data are never changed.</p>")


class PeriksaKoridor(_Base):
    QC_ONLY = True

    def name(self):
        return "periksa_koridor_ganda"

    def displayName(self):
        return "Check Stacked Corridors (report only)"

    def shortDescription(self):
        return "Marks duplicate and partly parallel lines, ends, junctions and gaps without changing the data."

    def shortHelpString(self):
        return ("<p><b>Check without changing data</b>: marks lines that duplicate or partly run parallel to a "
                "higher-priority line, free ends, junctions and gaps between strands. Same rules as Consolidate; "
                "useful as QC before consolidating. The report is written in Indonesian.</p>")
