# -*- coding: utf-8 -*-
"""
Seuntai - deteksi otomatis: kolom tanggal pembuatan, kolom produk/LOB, kolom identitas kabel, nilai produk, dan
aturan berkas mana yang layak diproses. Murni Python (tanpa QGIS) agar bisa diuji.

Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-3.0-or-later with section 7 terms (see LICENSE).
"""
import os
import re

try:
    from . import core as C
except ImportError:  # uji di luar paket
    import core as C

# Nama kolom dinormalkan: huruf besar, tanpa spasi/garis bawah/tanda hubung.
DATE_NAMES = ["CREATEDATE", "CREATEDDATE", "CREATED", "CREATEDAT", "CREATIONDATE", "DATECREATED", "CREATEDON",
              "TGLDIBUAT", "TANGGALDIBUAT", "TGLBUAT", "TANGGALBUAT", "TGLPEMBUATAN", "TANGGALPEMBUATAN",
              "INSTALLDATE", "TGLINSTALASI", "TANGGALINSTALASI", "BUILDDATE", "DATEBUILT", "TGLBANGUN",
              "TANGGAL", "TGL", "DATE"]
PRODUCT_NAMES = ["PRODUCT", "LOB", "PRODUK", "LINEOFBUSINESS", "PRODUCTLOB", "JENISPRODUK", "PRODUCTTYPE"]
IDENT_NAMES = ["NAME", "NAMA", "CABLENAME", "NAMAKABEL", "CABLEID", "IDKABEL", "KABEL", "CABLE"]
# Kata yang menandai kolom tanggal ubah/hapus (bukan tanggal pembuatan) -> tidak dipilih otomatis.
NOT_CREATE = ("EDIT", "MODIF", "UPDATE", "UBAH", "DELETE", "HAPUS", "LAST", "CHANGE")

OUTPUT_FIELDS = {"SUSTATUS", "SUURUTAN", "SUTANGGAL", "SUDIPAKAI"}
OUTPUT_SUFFIX = ("_kabel_tunggal", "_untai", "_keputusan", "_catatan")
VECTOR_EXT = (".shp", ".gpkg", ".geojson", ".json", ".kml", ".kmz", ".gml", ".tab", ".sqlite", ".fgb")
SKIP_DIRS = {"windows", "program files", "program files (x86)", "programdata", "appdata", "$recycle.bin",
             "system volume information", "node_modules", ".git", "__pycache__", "site-packages", "recovery",
             "perflogs", "msocache", "$windows.~bt", "$windows.~ws", "onedrivetemp", ".cache", ".conda",
             "anaconda3", "miniconda3"}


def norm(name):
    return re.sub(r"[\s_\-\.]+", "", str(name or "")).upper()


def _by_name(names, wanted):
    idx = {}
    for n in names:
        idx.setdefault(norm(n), n)
    for w in wanted:
        if w in idx:
            return idx[w]
    return None


def date_ratio(values, dayfirst=True):
    """Bagian nilai tidak kosong yang terbaca sebagai tanggal (0..1) dan jumlah nilai tidak kosong."""
    vals = [v for v in values if v not in (None, "") and str(v).upper() not in ("NULL", "NONE")]
    if not vals:
        return 0.0, 0
    ok = sum(1 for v in vals if C.parse_date(v, dayfirst) is not None)
    return ok / float(len(vals)), len(vals)


def pick_date_field(fields, samples, dayfirst=True):
    """fields: [(nama, jenis_tipe_teks)], samples: {nama: [nilai...]}. Hasil: (nama | None, alasan).
    Urutan: nama kolom yang dikenal (CREATEDATE, TANGGAL, ...) yang isinya >= 80% terbaca tanggal; lalu kolom
    bertipe Date/DateTime; lalu kolom teks yang >= 90% isinya terbaca tanggal. Kolom tanggal ubah/hapus dilewati."""
    names = [f[0] for f in fields]
    known = {}
    for n in names:
        known.setdefault(norm(n), n)
    for w in DATE_NAMES:
        n = known.get(w)
        if n is None:
            continue
        r, k = date_ratio(samples.get(n, []), dayfirst)
        if k == 0 or r >= 0.8:
            return n, "nama kolom dikenal (%s)" % n
    cands = []
    for n, typ in fields:
        if any(b in norm(n) for b in NOT_CREATE):
            continue
        t = str(typ or "").lower()
        r, k = date_ratio(samples.get(n, []), dayfirst)
        if ("date" in t or "time" in t) and (k == 0 or r >= 0.8):
            cands.append((0, -r, names.index(n), n, "kolom bertipe tanggal (%s)" % n))
        elif k >= 5 and r >= 0.9 and not _numeric_only(samples.get(n, [])):
            cands.append((1, -r, names.index(n), n, "isi %d%% terbaca tanggal (%s)" % (round(r * 100), n)))
    if cands:
        cands.sort()
        return cands[0][3], cands[0][4]
    return None, "tidak ada kolom tanggal pembuatan"


def _numeric_only(values):
    """Angka murni (mis. ID 20191030) bukan tanggal."""
    vals = [v for v in values if v not in (None, "")]
    return bool(vals) and all(isinstance(v, (int, float)) or re.fullmatch(r"\d+(\.\d+)?", str(v).strip())
                              for v in vals)


def pick_product_field(names):
    return _by_name(names, PRODUCT_NAMES)


def pick_ident_field(names):
    return _by_name(names, IDENT_NAMES)


def choose_values(counts, wanted):
    """counts: {nilai_produk: jumlah}, wanted: ['FTTT', ...] (kosong = semua).
    Hasil: (dipakai: list | None, pesan, ok). None = tanpa filter (semua garis)."""
    if not wanted:
        return None, "semua garis (tanpa filter produk)", True
    up = {}
    for v, n in counts.items():
        key = str(v).strip().upper()
        up[key] = up.get(key, 0) + n
    hit = [w for w in wanted if w.strip().upper() in up]
    if hit:
        n = sum(up[w.strip().upper()] for w in hit)
        return hit, "produk %s (%d garis)" % (", ".join(hit), n), True
    top = sorted(up.items(), key=lambda kv: -kv[1])[:6]
    isi = ", ".join("%s %d" % (k or "<kosong>", n) for k, n in top) or "-"
    return [], "tidak ada produk %s (isi kolom: %s)" % (", ".join(wanted), isi), False


def is_output_name(path_or_name):
    b = os.path.splitext(os.path.basename(str(path_or_name)))[0].lower()
    return b.endswith(OUTPUT_SUFFIX)


def is_output_fields(names):
    return len(OUTPUT_FIELDS & {norm(n) for n in names}) >= 2


def skip_dir(name):
    n = name.lower()
    return n in SKIP_DIRS or n.startswith("hasil_seuntai") or n.startswith(".")


def find_files(roots, max_files=5000, cancel=None, progress=None):
    """Telusuri folder (rekursif) dan kembalikan berkas vektor kandidat, urut abjad, tanpa folder hasil Seuntai
    dan folder sistem. Hasil: (daftar_path, terpotong: bool)."""
    out, seen = [], set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for d, dirs, files in os.walk(root, topdown=True, onerror=lambda e: None):
            if cancel and cancel():
                return sorted(out), False
            dirs[:] = sorted(x for x in dirs if not skip_dir(x))
            if progress:
                progress(d)
            for f in sorted(files):
                if f.lower().endswith(VECTOR_EXT) and not is_output_name(f):
                    p = os.path.normcase(os.path.abspath(os.path.join(d, f)))
                    if p in seen:
                        continue
                    seen.add(p)
                    out.append(os.path.join(d, f))
                    if len(out) >= max_files:
                        return sorted(out), True
    return sorted(out), False


def safe_name(s, used):
    base = re.sub(r"[^A-Za-z0-9_\-]+", "_", s).strip("_")[:60] or "data"
    name, i = base, 2
    while name.lower() in used:
        name = "%s_%d" % (base, i)
        i += 1
    used.add(name.lower())
    return name
