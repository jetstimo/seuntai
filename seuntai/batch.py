# -*- coding: utf-8 -*-
"""
Seuntai Otomatis - cari semua data kabel di folder (atau di seluruh folder pengguna / komputer), kenali kolomnya
sendiri, lalu proses satu per satu dengan aturan yang sama. Satu data gagal tidak menghentikan data lain.

Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-3.0-or-later with section 7 terms (see LICENSE).
"""
import datetime as _dt
import gc
import glob
import os
import string
import time
import traceback

from qgis.core import (QgsFeatureRequest, QgsProcessingAlgorithm, QgsProcessingContext,
                       QgsProcessingException, QgsProcessingMultiStepFeedback, QgsProcessingOutputNumber,
                       QgsProcessingOutputString, QgsProcessingParameterBoolean, QgsProcessingParameterEnum,
                       QgsProcessingParameterFile, QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterNumber, QgsProcessingParameterString, QgsProject, QgsVectorLayer,
                       QgsWkbTypes)
from qgis.PyQt.QtGui import QIcon

from . import compat as K
from . import deteksi as D
from . import ringkasan as RS
from .alg_strand import __version__, __author__, integrity_status
from . import _log

HERE = os.path.dirname(__file__)
LINGKUP = ["The chosen folder (including subfolders)",
           "User folders: Downloads, Documents, Desktop, OneDrive (slower)",
           "Whole computer: all drives (slowest)"]
LINGKUP_ID = ["folder", "folder pengguna", "seluruh komputer"]
MAX_LOAD = 25           # batas layer kabel tunggal yang dimuat ke peta (sisanya tetap tersimpan di folder hasil)


def _home_roots():
    h = os.path.expanduser("~")
    roots = [os.path.join(h, n) for n in ("Downloads", "Documents", "Desktop")]
    roots += sorted(glob.glob(os.path.join(h, "OneDrive*")))
    return [r for r in roots if os.path.isdir(r)]


def _drives():
    if os.name == "nt":
        return ["%s:\\" % d for d in string.ascii_uppercase if os.path.isdir("%s:\\" % d)]
    return ["/"]


def _sublayers(path):
    """[(uri, label)] untuk satu berkas: shapefile = 1 layer; GeoPackage/KML/GML bisa berisi beberapa layer."""
    out = []
    try:
        from qgis.core import QgsProviderRegistry
        subs = QgsProviderRegistry.instance().querySublayers(path)
        for s in subs:
            if s.providerKey() != "ogr":
                continue
            out.append((s.uri(), s.name() or os.path.splitext(os.path.basename(path))[0]))
    except Exception:
        out = []
    if not out:
        out = [(path, os.path.splitext(os.path.basename(path))[0])]
    return out


def inspect(uri, label, wanted, skip_nodate=False):
    """Periksa satu layer. Hasil dict: status SIAP/DILEWATI + alasan (Indonesia, untuk ringkasan) dan reason
    (Inggris, untuk log Processing), kolom yang terdeteksi, dan nilai produk. Data tanpa kolom tanggal pembuatan
    tetap diproses (garis terpanjang, ditandai nodate) kecuali skip_nodate=True."""
    info = {"path": uri.split("|")[0], "uri": uri, "label": label, "status": RS.SKIP, "alasan": "", "reason": ""}

    def skip(id_txt, en_txt):
        info["alasan"], info["reason"] = id_txt, en_txt
        return info
    lyr = QgsVectorLayer(uri, label, "ogr")
    try:
        if not lyr.isValid():
            return skip("tidak bisa dibuka sebagai layer vektor", "cannot be opened as a vector layer")
        if QgsWkbTypes.geometryType(lyr.wkbType()) != K.GEOM_LINE:
            return skip("bukan garis (titik/poligon/tabel)", "not lines (points/polygons/table)")
        n = lyr.featureCount()
        info["n_fitur"] = max(n, 0)
        if n == 0:
            return skip("layer kosong", "empty layer")
        names = [f.name() for f in lyr.fields()]
        if D.is_output_name(label) or D.is_output_name(info["path"]) or D.is_output_fields(names):
            return skip("berkas hasil Seuntai sebelumnya", "a previous Seuntai result")
        if not lyr.crs().isValid():
            return skip("CRS tidak diketahui (berkas .prj hilang)", "unknown CRS (.prj file missing)")
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
        f_tgl, why = D.pick_date_field([(f.name(), f.typeName()) for f in lyr.fields()], smp)
        info["kolom_tanggal"] = f_tgl or ""
        info["kolom_id"] = D.pick_ident_field(names) or ""
        info["nodate"] = not f_tgl
        if not f_tgl and skip_nodate:
            return skip("tidak ada kolom tanggal pembuatan (kolom: %s)" % ", ".join(names[:12]),
                        "no creation-date column (columns: %s)" % ", ".join(names[:12]))
        f_prod = D.pick_product_field(names)
        info["kolom_produk"] = f_prod or ""
        if wanted:
            if not f_prod:
                return skip("tidak ada kolom produk/LOB untuk memilih %s" % ", ".join(wanted),
                            "no product/LOB column to select %s" % ", ".join(wanted))
            counts = {}
            idx = lyr.fields().indexOf(f_prod)
            req2 = QgsFeatureRequest()
            try:
                req2.setFlags(K.REQ_NOGEOM)
                req2.setSubsetOfAttributes([idx])
            except Exception as _e:
                _log.note(_e)
            for ft in lyr.getFeatures(req2):
                v = ft[f_prod]
                v = "" if v is None or str(v) == "NULL" else str(v).strip()
                counts[v] = counts.get(v, 0) + 1
            vals, msg, ok = D.choose_values(counts, wanted)
            info["pilihan"] = msg
            if not ok:
                top = ", ".join("%s %d" % (k or "<empty>", c) for k, c in sorted(counts.items(), key=lambda kv: -kv[1])[:6])
                return skip(msg, "no product %s (values: %s)" % (", ".join(wanted), top or "-"))
            info["nilai"] = vals
        else:
            info["pilihan"] = "semua garis (tanpa filter produk)"
            info["nilai"] = []
        info["status"] = RS.PLAN
        if f_tgl:
            info["alasan"] = "kolom tanggal: %s (%s)" % (f_tgl, why)
            info["reason"] = "date column: %s" % f_tgl
            info["dasar"] = "TANGGAL"
        else:
            info["alasan"] = "TANPA TANGGAL PEMBUATAN: garis terpanjang per koridor dipakai"
            info["reason"] = "NO CREATION-DATE COLUMN: the longest line per corridor is kept"
            info["dasar"] = "PANJANG"
        return info
    finally:
        del lyr


class OtomatisSeuntai(QgsProcessingAlgorithm):
    FOLDER = "FOLDER"
    SCOPE = "SCOPE"
    PRODUK = "PRODUCT_VALUES"
    OUTDIR = "OUTPUT_FOLDER"
    LISTONLY = "LIST_ONLY"
    LOAD = "LOAD_RESULTS"
    OPEN = "OPEN_SUMMARY"
    TOL = "TOLERANCE"
    SMART = "SMART_GAP"
    MAXF = "MAX_FILES"
    SKIPND = "SKIP_NO_DATE"

    def createInstance(self):
        return OtomatisSeuntai()

    def name(self):
        return "otomatis"

    def displayName(self):
        return "Consolidate All Line Data in a Folder"

    def group(self):
        return ""

    def groupId(self):
        return ""

    def icon(self):
        return QIcon(os.path.join(HERE, "icon.png"))

    def shortDescription(self):
        return "Pick a folder and click Run: every line dataset in it is consolidated with the same rules."

    def shortHelpString(self):
        return (
            "<p><b>How to use</b>: pick a folder and click <b>Run</b>. Seuntai finds every line dataset in the folder "
            "and its subfolders (Shapefile, GeoPackage, GeoJSON, KML, ...), detects the creation-date, product/LOB "
            "and cable-name columns, and processes each dataset in turn.</p>"
            "<p><b>Output</b> (folder <code>Hasil_Seuntai_&lt;date&gt;</code>): one subfolder per dataset with the "
            "single-line Shapefile and report, plus a summary (HTML, CSV for Excel). Datasets without a creation-date "
            "column are processed with a warning and the longest line is kept (files end in "
            "<code>_TANPA_TANGGAL</code>). Datasets that do not fit are skipped with the reason; one failing dataset "
            "never stops the others.</p>"
            "<p><b>Advanced</b>: product/LOB values (empty = all), search scope, tolerance, skip datasets without a "
            "date, list only. Reports are written in Indonesian.</p>")

    def initAlgorithm(self, config=None):
        # Form utama hanya 1 isian (folder); sisanya di "Advanced".
        self.addParameter(QgsProcessingParameterFile(
            self.FOLDER, "Data folder (all line datasets inside are found automatically)",
            behavior=_folder_behavior(), optional=True))
        for prm in (
                QgsProcessingParameterString(
                    self.PRODUK, "Product/LOB values to keep, comma-separated (empty = all lines)", "", optional=True),
                QgsProcessingParameterEnum(self.SCOPE, "Search scope", LINGKUP, defaultValue=0),
                QgsProcessingParameterBoolean(
                    self.SKIPND, "Skip datasets without a creation-date column (default: warn and keep the longest line)",
                    False),
                QgsProcessingParameterBoolean(
                    self.LISTONLY, "Only list the datasets found (do not process yet)", False),
                QgsProcessingParameterFolderDestination(
                    self.OUTDIR, "Output folder (empty = 'Hasil_Seuntai_<date>' inside the data folder)",
                    optional=True, createByDefault=False),
                QgsProcessingParameterBoolean(self.LOAD, "Show the single-line layers on the map", True),
                QgsProcessingParameterBoolean(self.OPEN, "Open the summary when finished", True),
                QgsProcessingParameterNumber(
                    self.TOL, "Corridor half-width (m; default 7.5 = 15 m corridor)", K.NUM_DOUBLE, 7.5, False, 0.01,
                    1000.0),
                QgsProcessingParameterNumber(
                    self.SMART, "Join collinear gaps / gaps within the same cable up to (m, 0 = off)", K.NUM_DOUBLE,
                    10.0, False, 0.0, 1000.0),
                QgsProcessingParameterNumber(
                    self.MAXF, "Maximum number of files to inspect", K.NUM_INT, 5000, False, 1, 1000000)):
            self.addParameter(K.advanced(prm))
        for name, desc in (("N_DITEMUKAN", "Line datasets found"), ("N_BERHASIL", "Processed"),
                           ("N_DILEWATI", "Skipped"), ("N_GAGAL", "Failed"), ("N_TANPA_TGL", "Processed without a date")):
            self.addOutput(QgsProcessingOutputNumber(name, desc))
        self.addOutput(QgsProcessingOutputString("RINGKASAN", "Summary HTML"))
        self.addOutput(QgsProcessingOutputString("FOLDER_HASIL", "Output folder"))

    # ------------------------------------------------------------------ proses
    def processAlgorithm(self, parameters, context, feedback):
        t0 = time.time()
        folder = (self.parameterAsFile(parameters, self.FOLDER, context) or "").strip()
        scope = self.parameterAsEnum(parameters, self.SCOPE, context)
        wanted = [v.strip() for v in (self.parameterAsString(parameters, self.PRODUK, context) or "").split(",")
                  if v.strip()]
        list_only = self.parameterAsBool(parameters, self.LISTONLY, context)
        tol = self.parameterAsDouble(parameters, self.TOL, context)
        smart = self.parameterAsDouble(parameters, self.SMART, context)
        max_files = self.parameterAsInt(parameters, self.MAXF, context)
        skip_nd = self.parameterAsBool(parameters, self.SKIPND, context)
        if scope == 0:
            if not folder or not os.path.isdir(folder):
                raise QgsProcessingException("Pick a data folder first, or set 'Search scope' (Advanced) to the "
                                             "user folders or the whole computer.")
            roots = [folder]
            where = where_id = folder
        elif scope == 1:
            roots = _home_roots()
            where = "user folders (%s)" % ", ".join(os.path.basename(r) for r in roots)
            where_id = "folder pengguna (%s)" % ", ".join(os.path.basename(r) for r in roots)
        else:
            roots = _drives()
            where = "whole computer (%s)" % ", ".join(roots)
            where_id = "seluruh komputer (%s)" % ", ".join(roots)

        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M")
        outdir = self.parameterAsString(parameters, self.OUTDIR, context)
        try:
            from qgis.core import QgsProcessingUtils
            tmp = os.path.normcase(os.path.abspath(QgsProcessingUtils.tempFolder()))
        except Exception:
            tmp = None
        if (not outdir or outdir.upper().startswith("TEMPORARY")
                or (tmp and os.path.normcase(os.path.abspath(outdir)).startswith(tmp))):
            base = folder if scope == 0 else os.path.join(os.path.expanduser("~"), "Documents")
            outdir = os.path.join(base, "Hasil_Seuntai_" + stamp)
        os.makedirs(outdir, exist_ok=True)

        # ---- 1. cari berkas
        feedback.setProgressText("Searching for data in %s ..." % where)
        last = [0.0]

        def prog(d):
            if time.time() - last[0] > 1.0:
                last[0] = time.time()
                feedback.setProgressText("Searching: %s" % d)
        files, cut = D.find_files(roots, max_files, feedback.isCanceled, prog)
        if feedback.isCanceled():
            return {}
        if cut:
            feedback.pushWarning("Search stopped at %d files (limit). Raise 'Maximum number of files to inspect' "
                                 "under Advanced if needed." % max_files)
        feedback.pushInfo("Found %d vector files; checking their contents..." % len(files))

        # ---- 2. periksa tiap layer
        rows = []
        for i, p in enumerate(files):
            if feedback.isCanceled():
                return {}
            feedback.setProgress(10.0 * i / max(len(files), 1))
            for uri, label in _sublayers(p):
                try:
                    info = inspect(uri, label, wanted, skip_nd)
                except Exception as e:
                    info = {"path": p, "uri": uri, "label": label, "status": RS.SKIP,
                            "alasan": "tidak bisa dibuka (%s)" % e, "reason": "cannot be opened (%s)" % e}
                # hanya data garis yang relevan dicantumkan; titik/poligon/tabel dan berkas .json/.sqlite non-spasial
                # (konfigurasi, basis data aplikasi) tidak memenuhi ringkasan
                if info["alasan"].startswith("bukan garis") or (
                        info["alasan"].startswith("tidak bisa dibuka") and p.lower().endswith((".json", ".sqlite"))):
                    continue
                if scope == 0:
                    try:
                        info["rel"] = os.path.relpath(info["path"], folder)
                    except ValueError as _e:
                        _log.note(_e)
                rows.append(info)
        plan = [r for r in rows if r["status"] == RS.PLAN]
        feedback.pushInfo("%d line datasets: %d ready, %d skipped." % (len(rows), len(plan), len(rows) - len(plan)))
        for r in rows:
            if r["status"] != RS.PLAN:
                feedback.pushInfo("  skipped: %s - %s" % (r["path"], r.get("reason") or r["alasan"]))
        for r in plan:
            if r.get("nodate"):
                feedback.pushWarning("NO CREATION-DATE COLUMN in %s: stacked lines are still reduced to one, but the "
                                     "longest line is kept instead of the oldest (output files end in _TANPA_TANGGAL)."
                                     % r["path"])

        # ---- 3. proses satu per satu
        loaded = 0
        if not list_only and plan:
            import processing
            used = set()
            multi = QgsProcessingMultiStepFeedback(len(plan), feedback)
            for k, r in enumerate(plan):
                if feedback.isCanceled():
                    break
                multi.setCurrentStep(k)
                feedback.setProgressText("(%d/%d) %s" % (k + 1, len(plan), r["label"]))
                sub = os.path.join(outdir, D.safe_name(r["label"], used))
                os.makedirs(sub, exist_ok=True)
                rpt = os.path.join(sub, "Laporan_Seuntai_%s.html" % os.path.basename(sub))
                params = {"INPUT": r["uri"], "FIELD_PRODUCT": r.get("kolom_produk") or None,
                          "PRODUCT_VALUES": ",".join(r.get("nilai") or []),
                          "FIELD_DATE": r["kolom_tanggal"] or None, "SKIP_NO_DATE": False,
                          "FIELD_CABLE_ID": r.get("kolom_id") or None, "TOLERANCE": tol, "SMART_GAP": smart,
                          "SINGLE_LINES": "TEMPORARY_OUTPUT", "OUTPUT": "TEMPORARY_OUTPUT",
                          "SEGMENTS": "TEMPORARY_OUTPUT", "NOTES": "TEMPORARY_OUTPUT", "REPORT": rpt,
                          "SHP_FOLDER": sub, "OPEN_REPORT": False}
                t1 = time.time()
                try:
                    res = processing.run("seuntai:konsolidasi_strand", params, context=context, feedback=multi,
                                         is_child_algorithm=True)
                    r.update({"status": RS.OK, "n_input": int(res.get("N_INPUT") or 0),
                              "n_kabel": int(res.get("N_KABEL") or 0), "n_dup": int(res.get("N_DUPLIKAT") or 0),
                              "len_in": float(res.get("PANJANG_AWAL_M") or 0.0),
                              "len_kabel": float(res.get("PANJANG_KABEL_M") or 0.0),
                              "n_celah": int(res.get("N_CELAH") or 0), "tertua": res.get("TERTUA") or "",
                              "laporan": rpt if os.path.exists(rpt) else "",
                              "dasar": res.get("DASAR_URUTAN") or r.get("dasar") or "",
                              "nodate": (res.get("DASAR_URUTAN") == "PANJANG") or r.get("nodate", False)})
                    shp = sorted(glob.glob(os.path.join(sub, "*_kabel_tunggal.shp")))
                    r["kabel_shp"] = shp[0] if shp else ""
                    r["alasan"] = ("TANPA TANGGAL PEMBUATAN: garis terpanjang per koridor dipakai"
                                   if r.get("nodate") else "")
                except Exception as e:
                    if feedback.isCanceled():
                        r.update({"status": RS.SKIP, "alasan": "dibatalkan pengguna", "reason": "cancelled by the user"})
                        break
                    r.update({"status": RS.FAIL, "alasan": str(e).strip().splitlines()[0][:300] if str(e).strip()
                              else repr(e)})
                    feedback.reportError("Could not process %s: %s" % (r["path"], r["alasan"]), False)
                    feedback.pushDebugInfo(traceback.format_exc())
                r["detik"] = time.time() - t1
                # lepaskan layer sementara hasil data ini agar memori tidak menumpuk pada ratusan data
                try:
                    context.temporaryLayerStore().removeAllMapLayers()
                except Exception as _e:
                    _log.note(_e)
                gc.collect()
            for r in plan:
                if r["status"] == RS.PLAN:
                    r.update({"status": RS.SKIP, "alasan": "dibatalkan pengguna", "reason": "cancelled by the user"})
            # muat kabel tunggal ke peta (dibatasi agar QGIS tetap ringan)
            if self.parameterAsBool(parameters, self.LOAD, context):
                for r in [x for x in plan if x["status"] == RS.OK and x.get("kabel_shp")][:MAX_LOAD]:
                    try:
                        from . import styles
                        det = QgsProcessingContext.LayerDetails("Kabel tunggal - %s%s" % (
                            r["label"], " (TANPA TANGGAL)" if r.get("nodate") else ""),
                                                                QgsProject.instance(), "")
                        pp = styles.PostProcessor("kabel")
                        _KEEP.append(pp)
                        det.setPostProcessor(pp)
                        context.addLayerToLoadOnCompletion(r["kabel_shp"], det)
                        loaded += 1
                    except Exception as _e:
                        _log.note(_e)

        # ---- 4. ringkasan
        meta = {"waktu": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "lingkup": where_id,
                "produk": ", ".join(wanted) if wanted else "semua", "versi": __version__,
                "pencipta": "%s | integritas %s" % (__author__, integrity_status()),
                "durasi": time.time() - t0, "list_only": list_only, "tol": tol}
        html_p = RS.build_html(os.path.join(outdir, "Ringkasan_Seuntai.html"), rows, meta)
        RS.build_csv(os.path.join(outdir, "Ringkasan_Seuntai.csv"), rows)
        RS.build_readme(os.path.join(outdir, "BACA_SAYA.txt"), rows, meta)
        tt = RS.totals(rows)
        n_nd = sum(1 for r in rows if r["status"] == RS.OK and r.get("nodate"))
        feedback.pushInfo("Done: %d processed (%d without a creation date), %d skipped, %d failed." % (
            tt["ok"], n_nd, tt["skip"], tt["fail"]) if not list_only else
            "%d datasets ready, %d skipped (list only)." % (tt["plan"], tt["skip"]))
        feedback.pushInfo("Summary: %s" % html_p)
        if loaded and tt["ok"] > loaded:
            feedback.pushInfo("%d single-line layers loaded on the map; the rest are in the output folder." % loaded)
        self._open = html_p if self.parameterAsBool(parameters, self.OPEN, context) else None
        return {"N_DITEMUKAN": tt["found"], "N_BERHASIL": tt["ok"], "N_DILEWATI": tt["skip"], "N_GAGAL": tt["fail"],
                "N_TANPA_TGL": n_nd,
                "RINGKASAN": html_p, "FOLDER_HASIL": outdir}

    def postProcessAlgorithm(self, context, feedback):
        p = getattr(self, "_open", None)
        if p and os.path.exists(p):
            try:
                from qgis.PyQt.QtCore import QUrl
                from qgis.PyQt.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
            except Exception as _e:
                _log.note(_e)
        return {}


_KEEP = []


def _folder_behavior():
    for path in ("Qgis.ProcessingFileParameterBehavior.Folder", "QgsProcessingParameterFile.Folder"):
        try:
            obj = __import__("qgis.core", fromlist=["x"])
            for part in path.split("."):
                obj = getattr(obj, part)
            return obj
        except AttributeError as _e:
            _log.note(_e)
            continue
    return 1
