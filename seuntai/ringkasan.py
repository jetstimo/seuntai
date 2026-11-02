# -*- coding: utf-8 -*-
"""
Seuntai - ringkasan pemrosesan banyak data (HTML satu berkas, CSV untuk Excel, dan BACA_SAYA.txt).
Murni Python agar bisa diuji tanpa QGIS.

Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-2.0-or-later (see LICENSE).
"""
import csv
import html
import io
import os

try:
    from . import report as R
except ImportError:  # uji di luar paket
    import report as R

E = html.escape
OK, SKIP, FAIL, PLAN = "BERHASIL", "DILEWATI", "GAGAL", "SIAP"
LABEL = {OK: "Berhasil", SKIP: "Dilewati", FAIL: "Gagal", PLAN: "Siap diproses"}
COLOR = {OK: "#007A5A", SKIP: "#8A6100", FAIL: "#B3261E", PLAN: "#0B5CAD"}

FIX = [  # (kata kunci alasan, saran perbaikan)
    ("tidak ada produk", "Isi 'Produk yang diproses' dengan nilai yang ada di data (lihat isi kolom), atau kosongkan "
                         "untuk memproses semua garis."),
    ("tidak ada kolom produk", "Kosongkan isian 'Produk yang diproses' bila data ini memang tidak punya kolom "
                               "produk/LOB."),
    ("tidak ada kolom tanggal", "Data tanpa tanggal pembuatan tidak bisa memilih kabel tertua. Minta data yang "
                                "memuat kolom CREATEDATE, atau matikan opsi 'Skip datasets without a creation-date "
                                "column' agar garis terpanjang dipakai (ditandai TANPA TANGGAL)."),
    ("bukan garis", "Hanya data garis (kabel/jalur) yang diproses; data titik/poligon diabaikan."),
    ("hasil Seuntai", "Ini berkas hasil Seuntai sebelumnya; sengaja tidak diproses ulang."),
    ("CRS", "Atur CRS layer di QGIS (klik kanan layer > Layer CRS) lalu jalankan lagi."),
    ("kosong", "Layer tidak berisi fitur."),
    ("tidak bisa dibuka", "Berkas rusak, terkunci program lain, atau formatnya tidak didukung."),
]


def fix_for(reason):
    r = (reason or "").lower()
    for key, tip in FIX:
        if key.lower() in r:
            return tip
    return "Lihat pesan di kolom alasan; bila perlu jalankan alat 'Konsolidasi satu layer' untuk data ini."


def _rel(path, base):
    try:
        return os.path.relpath(path, base).replace(os.sep, "/")
    except ValueError:          # drive berbeda di Windows
        return "file:///" + path.replace(os.sep, "/")


def _km(m):
    """Panjang ringkas: >= 100 km tanpa desimal, >= 1 km satu desimal, di bawahnya meter."""
    if m >= 100000:
        return "%s km" % R._n(m / 1000.0, 0)
    if m >= 1000:
        return "%s km" % R._n(m / 1000.0, 1)
    return "%s m" % R._n(m, 0)


def _where(r):
    return r.get("rel") or r["path"]


def _oldest(s):
    if not s:
        return "-"
    name, _, date = s.partition(" | ")
    return "<b>%s</b><div class='sub'>%s</div>" % (E(name), E(date)) if date else E(s)


def totals(rows):
    ok = [r for r in rows if r["status"] == OK]
    return {
        "found": len(rows), "ok": len(ok), "skip": sum(1 for r in rows if r["status"] == SKIP),
        "fail": sum(1 for r in rows if r["status"] == FAIL), "plan": sum(1 for r in rows if r["status"] == PLAN),
        "n_in": sum(r.get("n_input", 0) for r in ok), "n_kabel": sum(r.get("n_kabel", 0) for r in ok),
        "n_dup": sum(r.get("n_dup", 0) for r in ok), "len_in": sum(r.get("len_in", 0.0) for r in ok),
        "len_kabel": sum(r.get("len_kabel", 0.0) for r in ok), "n_celah": sum(r.get("n_celah", 0) for r in ok),
    }


def headline(t, list_only):
    if list_only:
        return "%d data garis siap diproses, %d dilewati (lihat alasannya di bawah)." % (t["plan"], t["skip"])
    if not t["ok"]:
        return "Tidak ada data yang berhasil diproses dari %d data yang ditemukan." % t["found"]
    s = "%s data diproses: %s garis menjadi %s kabel tunggal tanpa tumpukan; %s garis duplikat dibuang." % (
        R._n(t["ok"]), R._n(t["n_in"]), R._n(t["n_kabel"]), R._n(t["n_dup"]))
    if t["skip"] or t["fail"]:
        s += " %d dilewati, %d gagal." % (t["skip"], t["fail"])
    return s


CSS = """
:root{--ink:#1A1033;--muted:#5B5670;--line:#E4E1EE;--bg:#FBFAFE;--card:#FFFFFF;--coral:#E0234E;--chip:#F3F1F9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 Inter,system-ui,
sans-serif}main{max-width:1180px;margin:0 auto;padding:28px 18px 60px}header{display:flex;gap:14px;align-items:center}
h1{font:800 26px/1.15 'Display',Inter,sans-serif;margin:0}h2{font-size:18px;margin:34px 0 10px}
.sub{color:var(--muted);font-size:13px}.lead{font-size:18px;font-weight:600;margin:18px 0 6px}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.k{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.k b{display:block;font-size:20px;white-space:nowrap}.k span{color:var(--muted);font-size:12.5px}
.tw{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{padding:8px 10px;border-bottom:1px solid var(--line);
text-align:left;vertical-align:top}th{background:var(--chip);font-weight:600;white-space:nowrap}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.st{font-weight:700;white-space:nowrap}code,.mono{font-family:'Plex Mono',ui-monospace,monospace;font-size:12.5px}
a{color:#0B5CAD}.path{color:var(--muted);font-size:12px;word-break:break-all}
.note{background:var(--card);border-left:4px solid var(--coral);padding:10px 14px;border-radius:8px;margin:12px 0}
dl{display:grid;grid-template-columns:190px 1fr;gap:6px 14px;margin:0}dt{font-weight:600}dd{margin:0}
footer{margin-top:40px;color:var(--muted);font-size:12.5px}
@media (prefers-color-scheme:dark){:root{--ink:#ECE9F7;--muted:#B3AEC8;--line:#353047;--bg:#16121F;--card:#1E1A2A;
--chip:#272236}a{color:#8CC2FF}}
@media (max-width:640px){dl{grid-template-columns:1fr}h1{font-size:22px}}
"""


def build_html(path, rows, meta):
    """rows: daftar dict per data; meta: dict(waktu, lingkup, folder, produk, versi, pencipta, durasi, list_only)."""
    base = os.path.dirname(path)
    t = totals(rows)
    lo = meta.get("list_only")
    fonts = R._font("Display", "display-800.woff", 800) + R._font("Inter", "inter-400.woff", 400) + \
        R._font("Inter", "inter-600.woff", 600) + R._font("Plex Mono", "plexmono-400.woff", 400)
    kp = [(R._n(t["found"]), "data garis ditemukan"),
          (R._n(t["plan"] if lo else t["ok"]), "siap diproses" if lo else "berhasil diproses"),
          (R._n(t["skip"]), "dilewati"), (R._n(t["fail"]), "gagal")]
    if not lo:
        kp += [("%s &rarr; %s" % (R._n(t["n_in"]), R._n(t["n_kabel"])), "garis masuk &rarr; kabel tunggal"),
               ("%s &rarr; %s" % (_km(t["len_in"]), _km(t["len_kabel"])), "panjang sebelum &rarr; sesudah"),
               (R._n(t["n_celah"]), "celah perlu dicek di lapangan/peta")]
    kpi = "".join("<div class='k'><b>%s</b><span>%s</span></div>" % (a, b) for a, b in kp)

    done = [r for r in rows if r["status"] in (OK, PLAN)]
    other = [r for r in rows if r["status"] in (SKIP, FAIL)]
    trs = []
    for i, r in enumerate(done, 1):
        if r["status"] == PLAN:
            trs.append("<tr><td class='n'>%d</td><td><b>%s</b><div class='path'>%s</div></td><td>%s</td><td>%s</td>"
                       "<td class='n'>%s</td><td>%s</td></tr>" % (
                           i, E(r["label"]), E(_where(r)), E(r.get("kolom_tanggal") or "-"),
                           E(r.get("pilihan") or "-"), R._n(r.get("n_fitur", 0)), E(r.get("kolom_id") or "-")))
            continue
        links = []
        if r.get("laporan"):
            links.append("<a href='%s'>Laporan</a>" % E(_rel(r["laporan"], base)))
        if r.get("kabel_shp"):
            links.append("<a href='%s'>Folder hasil</a>" % E(_rel(os.path.dirname(r["kabel_shp"]), base)))
        trs.append(
            "<tr><td class='n'>%d</td><td><b>%s</b><div class='path'>%s</div><div class='sub'>%s</div></td>"
            "<td class='n'>%s</td><td class='n'>%s</td><td class='n'>%s</td><td class='n'>%s &rarr; %s</td>"
            "<td>%s</td><td class='n'>%s</td><td class='n'>%s</td><td>%s</td></tr>" % (
                i, E(r["label"]), E(_where(r)),
                E(("TANPA TANGGAL PEMBUATAN: garis terpanjang dipakai; %s" % (r.get("pilihan") or "")) if r.get("nodate")
                  else "tanggal: %s; %s" % (r.get("kolom_tanggal") or "-", r.get("pilihan") or "")),
                R._n(r.get("n_input", 0)), R._n(r.get("n_kabel", 0)), R._n(r.get("n_dup", 0)),
                _km(r.get("len_in", 0.0)), _km(r.get("len_kabel", 0.0)), _oldest(r.get("tertua")),
                R._n(r.get("n_celah", 0)), R._n(r.get("detik", 0.0), 1), " &middot; ".join(links)))
    if lo:
        head = ("<tr><th>#</th><th>Data</th><th>Kolom tanggal</th><th>Yang diproses</th><th>Fitur</th>"
                "<th>Kolom nama kabel</th></tr>")
    else:
        head = ("<tr><th>#</th><th>Data</th><th>Garis masuk</th><th>Kabel tunggal</th><th>Duplikat dibuang</th>"
                "<th>Panjang sebelum &rarr; sesudah</th><th>Kabel tertua</th><th>Celah dicek</th><th>Detik</th>"
                "<th>Buka</th></tr>")
    t1 = "<div class='tw'><table>%s%s</table></div>" % (head, "".join(trs)) if done else \
        "<p class='sub'>Tidak ada.</p>"
    tro = "".join("<tr><td><b>%s</b><div class='path'>%s</div></td><td class='st' style='color:%s'>%s</td>"
                  "<td>%s</td><td>%s</td></tr>" % (E(r["label"]), E(_where(r)), COLOR[r["status"]],
                                                   LABEL[r["status"]], E(r.get("alasan") or ""),
                                                   E(fix_for(r.get("alasan"))))
                  for r in other)
    t2 = ("<div class='tw'><table><tr><th>Data</th><th>Status</th><th>Alasan</th><th>Cara memperbaiki</th></tr>%s"
          "</table></div>" % tro) if other else "<p class='sub'>Tidak ada.</p>"
    guide = """
<h2>Cara membaca hasil</h2>
<p>Setiap data punya folder sendiri berisi berkas berikut (bisa dibuka di QGIS, ArcGIS, atau Google Earth Pro):</p>
<dl>
<dt>*_kabel_tunggal.shp</dt><dd><b>Hasil utama.</b> Satu garis per jalur: garis dengan tanggal pembuatan paling
lama, tanpa tumpukan, dengan seluruh atribut aslinya.</dd>
<dt>*_untai.shp</dt><dd>Jaringan tersambung (untai) hasil gabungan, untuk menghitung panjang dan jumlah jaringan.</dd>
<dt>*_keputusan.shp</dt><dd>Semua garis masukan beserta keputusannya: dipakai, dipangkas, atau duplikat dibuang,
dan alasannya.</dd>
<dt>*_catatan.shp</dt><dd>Titik ujung, percabangan, celah, dan sambungan. Celah perlu dicek di peta/lapangan.</dd>
<dt>Laporan_Seuntai_*.html</dt><dd>Laporan lengkap satu data: peta sebelum/sesudah, kabel tertua, dan dasar
keputusan beserta sumbernya.</dd>
</dl>
<h2>Kolom tambahan di kabel tunggal</h2>
<dl>
<dt>su_status</dt><dd>DIPAKAI = garis dipakai utuh; DIPANGKAS = sebagian garis tumpang-tindih dengan garis yang lebih
tua sehingga hanya sisanya yang dipakai.</dd>
<dt>su_tanggal</dt><dd>Tanggal pembuatan yang terbaca (YYYY-MM-DD jam).</dd>
<dt>su_urutan</dt><dd>Urutan prioritas: 1 = tertua. Urutkan kolom ini untuk melihat kabel paling awal dibuat.</dd>
<dt>su_panjang / su_dipakai</dt><dd>Panjang garis asli dan panjang yang dipakai (meter, di permukaan bumi).</dd>
<dt>su_strand</dt><dd>Nomor untai (jaringan tersambung) tempat garis ini berada.</dd>
<dt>su_fid</dt><dd>Nomor fitur di data asli, untuk menelusuri kembali.</dd>
<dt>su_dasar</dt><dd>Dasar urutan: TANGGAL = garis dipilih karena tanggal pembuatannya paling lama; PANJANG = tanggal
pembuatan tidak ada/tidak terbaca sehingga garis terpanjang yang dipakai (berkas data tanpa tanggal diberi akhiran
_TANPA_TANGGAL).</dd>
</dl>"""
    doc = """<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1"><title>Ringkasan Seuntai</title><style>%s%s</style></head><body><main>
<header>%s<div><h1>Ringkasan Seuntai Otomatis</h1><div class="sub">%s &middot; %s &middot; Seuntai %s</div></div>
</header>
<p class="lead">%s</p>
<div class="sub">Lokasi pencarian: %s &middot; Produk: %s &middot; Durasi %s detik</div>
<div class="kpi">%s</div>
%s
<h2>%s</h2>%s
<h2>Data yang dilewati atau gagal</h2>%s
%s
<footer>Dibuat oleh Seuntai %s (%s). Setiap data diproses terpisah dengan aturan yang sama: garis di koridor yang
sama (&le; toleransi %s m) diwakili garis dengan tanggal pembuatan tertua; jalur unik tidak dibuang. Hasil tiap data
tidak bergantung pada data lain yang ikut diproses.</footer>
</main></body></html>""" % (
        fonts, CSS, R._logo(), E(meta.get("waktu", "")), "daftar saja (belum diproses)" if lo else "selesai",
        E(meta.get("versi", "")), E(headline(t, lo)), E(meta.get("lingkup", "")), E(meta.get("produk", "")),
        R._n(meta.get("durasi", 0.0), 1), kpi,
        ("<div class='note'>Ini daftar data yang ditemukan. Jalankan lagi tanpa centang 'Hanya cari dan tampilkan "
         "daftar' untuk memprosesnya.</div>") if lo else "",
        "Data siap diproses" if lo else "Data yang diproses", t1, t2, "" if lo else guide,
        E(meta.get("versi", "")), E(meta.get("pencipta", "")), R._n(meta.get("tol", 7.5), 1))
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


COLS = [("status", "Status"), ("label", "Data"), ("path", "Lokasi berkas"), ("alasan", "Alasan / catatan"),
        ("kolom_tanggal", "Kolom tanggal"), ("pilihan", "Yang diproses"), ("n_input", "Garis masuk"),
        ("n_kabel", "Kabel tunggal"), ("n_dup", "Duplikat dibuang"), ("len_in", "Panjang sebelum (m)"),
        ("len_kabel", "Panjang kabel tunggal (m)"), ("tertua", "Kabel tertua"), ("n_celah", "Celah dicek"),
        ("dasar", "Dasar urutan"), ("detik", "Detik"), ("kabel_shp", "Shapefile kabel tunggal"),
        ("laporan", "Laporan")]


def build_csv(path, rows):
    """CSV untuk Excel berbahasa Indonesia: pemisah titik koma, desimal koma, UTF-8 dengan BOM."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow([c[1] for c in COLS])
    for r in rows:
        out = []
        for k, _ in COLS:
            v = r.get(k, "")
            if k == "status":
                v = LABEL.get(v, v)
            if isinstance(v, float):
                v = ("%.2f" % v).replace(".", ",")
            out.append(v)
        w.writerow(out)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(buf.getvalue())
    return path


def build_readme(path, rows, meta):
    t = totals(rows)
    lines = [
        "SEUNTAI - HASIL PEMROSESAN OTOMATIS",
        "Waktu: %s | Seuntai %s | %s" % (meta.get("waktu", ""), meta.get("versi", ""), meta.get("pencipta", "")),
        "",
        headline(t, meta.get("list_only")),
        "",
        "Buka 'Ringkasan_Seuntai.html' untuk tabel lengkap, atau 'Ringkasan_Seuntai.csv' di Excel.",
        "",
        "Isi setiap folder data:",
        "  *_kabel_tunggal.shp  HASIL UTAMA: satu garis per jalur (tanggal pembuatan tertua), atribut asli utuh",
        "  *_untai.shp          jaringan tersambung hasil gabungan",
        "  *_keputusan.shp      semua garis masukan + keputusan (dipakai/dipangkas/duplikat) dan alasannya",
        "  *_catatan.shp        ujung, percabangan, celah (perlu dicek), sambungan",
        "  Laporan_Seuntai_*.html  laporan lengkap satu data",
        "",
        "Kolom su_urutan = 1 adalah kabel tertua. su_status: DIPAKAI (utuh) / DIPANGKAS (sebagian).",
        "Kolom su_dasar: TANGGAL (dipilih menurut tanggal pembuatan) / PANJANG (tanpa tanggal: garis terpanjang).",
        "Berkas berakhiran _TANPA_TANGGAL berasal dari data tanpa kolom tanggal pembuatan.",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return path
