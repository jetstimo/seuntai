# -*- coding: utf-8 -*-
"""
Seuntai - laporan HTML interaktif satu berkas (bekerja offline, bahasa Indonesia).

Isi: putusan dalam bahasa sederhana + daftar "siap dipakai?", angka utama, peta dengan tampilan Keputusan /
Sebelum / Sesudah / Bandingkan (geser), animasi "cara Seuntai bekerja", cerita per garis (mengapa dipakai,
dipangkas, atau dibuang, lengkap dengan garis pemiliknya), umur jaringan, tabel untai, keputusan per garis
(saring, cari, unduh CSV), daftar periksa celah yang tersimpan di peramban, profil data, tanya-jawab, kamus
istilah (penjelasan muncul saat istilah disentuh), tur singkat, parameter, serta dasar keputusan + sumber.

build() = collect() (data dari hasil proses) + render() (HTML murni dari data JSON), sehingga tampilan dapat
diuji tanpa QGIS.

Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-2.0-or-later (see LICENSE).
Leaflet 1.9.4 (BSD-2-Clause, assets/map/LEAFLET_LICENSE.txt); Inter dan IBM Plex Mono (SIL OFL 1.1).
"""
import base64
import html
import json
import math
import os

try:
    from . import core as C
    from . import sumber as SB
except ImportError:  # uji di luar paket
    import core as C
    import sumber as SB

HERE = os.path.dirname(__file__)
E = html.escape
MAX_VERTS = 250000

STATUS = [  # kode, label, warna (Okabe-Ito), pola (dash)
    ("DIPAKAI", "Dipakai utuh", "#009E73", ""),
    ("DIPANGKAS", "Dipangkas", "#E69F00", "8 6"),
    ("DUPLIKAT", "Duplikat dibuang", "#D55E00", "2 6"),
    ("SERPIHAN", "Serpihan dibuang", "#CC79A7", "2 6"),
    ("GEOMETRI_KOSONG", "Tanpa geometri", "#8C8C8C", "2 6"),
]
NOTE = [("CELAH", "Celah", "#D55E00"), ("JEMBATAN", "Dijembatani", "#C9B800"), ("CABANG", "Percabangan", "#0072B2"),
        ("UJUNG", "Ujung", "#3B3355")]

# Kamus istilah: kunci, istilah, penjelasan sederhana. Dipakai di bagian Kamus dan sebagai penjelasan melayang.
GLOSS = [
    ("koridor", "Koridor",
     "Jalur selebar dua kali toleransi di sekitar garis yang sudah dipakai (bawaan 2 x 7,5 m = 15 m, setara RUMIJA "
     "jalan sedang). Garis lain yang berjalan di dalam jalur ini dianggap menempati jalan yang sama."),
    ("toleransi", "Toleransi koridor",
     "Jarak terjauh ke kiri dan ke kanan sebuah garis yang masih dianggap 'jalur yang sama' (separuh lebar "
     "koridor). Bawaan 7,5 m: garis yang digambar bergeser beberapa meter di jalan yang sama tetap jadi satu. "
     "Pilihan 2,5 m (koridor 5 m) hanya menggabungkan salinan yang hampir berimpit."),
    ("rumija", "RUMIJA",
     "Ruang Milik Jalan: jalur tanah milik jalan, yaitu badan jalan, bahu, saluran, dan sejalur tanah di luarnya "
     "(PP 34/2006 Pasal 39). Lebar minimumnya: jalan kecil 11 m, jalan sedang 15 m, jalan raya 25 m, jalan bebas "
     "hambatan 30 m (Pasal 40). Kabel umumnya dipasang di dalam RUMIJA, sehingga lebar koridor Seuntai mengacu "
     "pada nilai ini."),
    ("prioritas", "Urutan prioritas",
     "Urutan pemeriksaan garis. Garis dengan tanggal pembuatan paling tua diperiksa lebih dulu dan menang bila "
     "koridornya sama. Tanggal sama: garis lebih panjang didahulukan. Tanggal kosong: paling akhir. Urutan 1 = "
     "paling diutamakan."),
    ("dipakai", "Dipakai utuh",
     "Garis tidak menumpuk dengan garis yang lebih diutamakan, atau hanya bersinggungan sedikit. Garis "
     "dipertahankan apa adanya, lengkap dengan atributnya."),
    ("dipangkas", "Dipangkas",
     "Sebagian garis berjalan sejajar dengan garis yang lebih diutamakan. Bagian sejajar itu dibuang, bagian yang "
     "unik (jalur yang hanya dimiliki garis ini) tetap dipakai dan disambungkan."),
    ("duplikat", "Duplikat",
     "Sebagian besar panjang garis (bawaan 80% atau lebih) berada di dalam koridor garis yang lebih diutamakan. "
     "Garis dianggap salinan dan tidak ikut di hasil. Data asli Anda tidak diubah."),
    ("serpihan", "Serpihan",
     "Sisa potongan yang terlalu pendek setelah dipangkas sehingga tidak berarti sebagai jalur kabel."),
    ("kabel", "Kabel tunggal",
     "Hasil utama: satu garis per koridor, yaitu garis yang menang (tertua) dengan seluruh atribut aslinya. "
     "Disimpan sebagai berkas ..._kabel_tunggal.shp."),
    ("untai", "Untai",
     "Jaringan garis hasil yang tersambung satu sama lain, digabung menjadi satu fitur. Satu untai bisa lurus atau "
     "bercabang."),
    ("fragmen", "Fragmen",
     "Untai yang sangat pendek (bawaan di bawah 25 m, separuh jarak antar tiang). Tetap ada di hasil tetapi "
     "ditandai agar mudah diperiksa."),
    ("celah", "Celah",
     "Ujung untai yang berhenti tidak jauh dari untai lain dan mengarah ke sana. Bisa memang terputus di lapangan, "
     "bisa juga kesalahan gambar. Perlu dilihat sebelum data dipakai."),
    ("jembatan", "Jembatan",
     "Celah kecil yang disambung otomatis karena jelas satu jalur: dua ujung segaris saling menghadap, atau "
     "ruas dari kabel bernama sama, sampai 10 m."),
    ("drift", "Pita drift",
     "Daerah di samping koridor sampai dua kali toleransi (bawaan 15 m) dari garis yang dipakai. Sisa garis yang "
     "berjalan sejajar seluruhnya di pita ini dianggap geseran gambar dari jalur yang sama, bukan kabel lain."),
    ("cabang", "Percabangan",
     "Titik tempat tiga garis atau lebih bertemu."),
    ("lutut", "Lutut kurva",
     "Titik pada grafik jarak antar-garis tempat kenaikan mulai melandai (metode Kneedle). Di bawah titik ini "
     "kebanyakan pasangan garis adalah tumpukan; toleransi yang baik berada sedikit di atasnya."),
    ("jalan", "Cocok ke jalan",
     "Seuntai mencocokkan setiap garis kabel ke garis tengah jalan terdekat (OpenStreetMap, diunduh otomatis). Dua "
     "garis di dua sisi jalan yang sama menunjuk ke tempat yang sama di jalan itu, sehingga dianggap satu jalur "
     "walaupun berjarak lebih dari lebar koridor. Gang atau jalan lain yang sejajar adalah ruas lain dan tidak ikut "
     "tergabung. Lebar pencarian mengikuti kelas jalan (RUMIJA): jalan arteri sampai 22 m dari garis tengah, jalan "
     "lingkungan 10 m, gang 5-6 m."),
    ("dasar", "su_dasar",
     "Kolom di hasil yang menjelaskan dasar urutan: TANGGAL = garis menang karena tanggal pembuatannya paling tua; "
     "PANJANG = tanggal tidak ada atau tidak terbaca, garis menang karena paling panjang."),
    ("utm", "UTM dan panjang elipsoidal",
     "Seuntai menghitung jarak dalam meter memakai zona UTM di lokasi data, dan panjang diukur di permukaan bumi. "
     "Hasil tetap sama apa pun sistem koordinat layer Anda."),
]
GLOSS_KEYS = {k for k, _t, _d in GLOSS}

FAQ = [
    ("Apakah data asli saya diubah?",
     "Tidak. Seuntai hanya membaca layer Anda. Semua hasil ditulis ke berkas baru (kabel tunggal, untai, keputusan, "
     "catatan) dan laporan ini."),
    ("Kenapa garis saya tidak ada di hasil?",
     "Kemungkinan besar garis itu duplikat: sebagian besar panjangnya menumpuk dengan garis lain yang lebih tua. Cari "
     "FID atau nama kabelnya di kotak pencarian peta atau di tabel Keputusan per garis, lalu buka ceritanya: di sana "
     "tertulis garis mana yang menang dan berapa persen yang menumpuk."),
    ("Kenapa yang dipilih garis tertua, bukan yang terbaru?",
     "Garis tertua biasanya adalah kabel yang pertama kali digelar; salinan berikutnya muncul dari digitasi ulang, "
     "ekspor, atau survei ulang di jalur yang sama. Urutan ini bisa dibalik (terbaru dulu) di pengaturan Advanced."),
    ("Apa arti TANPA_TANGGAL dan su_dasar = PANJANG?",
     "Data tidak punya kolom tanggal pembuatan yang terbaca, sehingga umur garis tidak bisa dibandingkan. Seuntai "
     "tetap menyisakan satu garis per koridor, tetapi yang dipilih adalah garis terpanjang. Bila data bertanggal "
     "tersedia, jalankan ulang untuk mendapatkan garis tertua."),
    ("Apa yang harus saya lakukan dengan celah?",
     "Buka bagian Celah, klik setiap baris untuk melihatnya di peta, lalu centang bila sudah diperiksa. Celah yang "
     "memang ada di lapangan dibiarkan; celah karena kesalahan gambar diperbaiki di data sumber."),
    ("Kenapa masih ada dua garis berdampingan?",
     "Dua garis dijadikan satu bila jaraknya tidak lebih dari separuh lebar koridor, atau bila keduanya mengikuti "
     "jalan yang sama di dua sisinya (pencocokan ke jalan OpenStreetMap). Garis yang tersisa berdampingan biasanya "
     "mengikuti jalan berbeda (mis. gang di belakang rumah), atau jalannya belum tercatat di OpenStreetMap. Periksa "
     "di citra satelit; bila memang satu jalur, pilih koridor yang lebih lebar."),
    ("Lebar koridor 15 m itu dari mana? Boleh diubah?",
     "15 m adalah lebar minimum RUMIJA jalan sedang (PP 34/2006 Pasal 40); kabel di jalan yang sama hampir selalu "
     "berada di dalamnya. Pilih 5 m bila kabel di dua sisi jalan harus tetap terpisah, atau 25 m untuk jalan raya. "
     "Bagian Kualitas data menunjukkan sebaran jarak antar-garis data Anda."),
    ("Bagaimana memakai hasilnya di QGIS?",
     "Pakai berkas ..._kabel_tunggal.shp sebagai jaringan bersih. Layer ..._keputusan.shp berisi semua garis "
     "masukan dengan kolom su_status dan su_alasan, berguna untuk memeriksa atau menelusuri satu garis."),
]


def _read(*p):
    with open(os.path.join(HERE, *p), "rb") as f:
        return f.read()


def _font(name, file, weight):
    try:
        b64 = base64.b64encode(_read("assets", "fonts", file)).decode()
        return ("@font-face{font-family:'%s';src:url(data:font/woff;base64,%s) format('woff');font-weight:%s;"
                "font-display:swap}" % (name, b64, weight))
    except OSError:
        return ""


def _logo():
    try:
        s = _read("icon.svg").decode("utf-8")
        return s.replace('width="256" height="256"', 'width="44" height="44" aria-hidden="true"')
    except OSError:
        return ""


def _n(x, d=0):
    s = ("{:,.%df}" % d).format(x)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _km(m):
    return ("%s km" % _n(m / 1000.0, 2)) if m >= 1000 else ("%s m" % _n(m, 0 if m >= 100 else 1))


def T(key, label=None):
    """Istilah dengan penjelasan melayang (lihat GLOSS)."""
    lab = label or next(t for k, t, _d in GLOSS if k == key)
    return "<span class='term' tabindex='0' data-t='%s'>%s</span>" % (key, E(lab))


def _val(v):
    if v is None:
        return ""
    s = str(v)
    return "" if s == "NULL" else s


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if o is None or isinstance(o, (str, int, bool)):
        return o
    return str(o)


# ======================================================================================================== data
def collect(meta, stats, res, strands, notes, wgs, feats, f_prod):
    """Kumpulkan semua data laporan sebagai struktur JSON biasa."""
    order = res["order"]
    total_v = sum(len(p) for r in order for p in r.parts) + sum(len(p) for s in strands for p in s["lines"])
    stride = max(1, int(total_v / MAX_VERTS) + (1 if total_v > MAX_VERTS else 0))

    def thin(pts):
        if stride == 1 or len(pts) <= 3:
            return pts
        return [pts[0]] + pts[1:-1:stride] + [pts[-1]]

    def ll(pts):
        return [[round(y, 7), round(x, 7)] for x, y in wgs(thin(pts))]

    f_id = meta.get("f_id") or ""
    segs = []
    for r in order:
        f = feats[r.fid]
        segs.append({"f": str(r.fid), "s": r.status, "r": r.rank, "L": round(getattr(r, "len_e", r.length), 1),
                     "k": round(getattr(r, "kept_e", r.kept_len), 1), "c": float("%.0f" % (r.cover * 100)),
                     "d": "" if r.dup_of is None else str(r.dup_of),
                     "t": r.date.strftime("%Y-%m-%d") if r.date else "", "n": r.note,
                     "g": "" if r.group is None else str(r.group),
                     "p": "" if not f_prod else _val(f[f_prod]),
                     "nm": "" if not f_id else _val(f[f_id]),
                     "x": [ll(p) for p in r.parts]})
    sid_of = {}
    for s in strands:
        for o in s["owners"]:
            sid_of.setdefault(str(o), s["id"])
    for sg in segs:
        sg["u"] = sid_of.get(sg["f"], "")
    sts = []
    for s in strands:
        sts.append({"i": s["id"], "g": "" if s["grp"] is None else str(s["grp"]), "k": s.get("kelas", "UTAMA"),
                    "j": round(s.get("jembatan", 0.0), 1),
                    "L": round(s.get("length", 0.0), 1), "u": bool(s.get("utuh")), "o": len(s.get("owners_sorted", [])),
                    "fo": [str(o) for o in s.get("owners_sorted", [])][:400], "r": len(s["lines"]),
                    "e": s.get("n_ujung", 0), "b": s.get("n_cabang", 0),
                    "t0": s["date_min"].strftime("%Y-%m-%d") if s.get("date_min") else "",
                    "x": [ll(p) for p in s["lines"]]})
    nts = []
    for jenis, p, sid, grp, d, ket in notes:
        (x, y), = wgs([p])
        nts.append({"j": jenis, "a": round(y, 7), "o": round(x, 7), "i": sid, "d": None if d is None else round(d, 2),
                    "k": ket, "g": "" if grp is None else str(grp)})
    st = {k: v for k, v in stats.items() if k not in ("kscale",)}
    return _jsonable({"meta": meta, "stats": st, "stride": stride,
                      "data": {"S": sts, "G": segs, "N": nts}})


def build(path, meta, stats, res, strands, notes, wgs, feats, f_prod, rec_by=None):
    return render(path, collect(meta, stats, res, strands, notes, wgs, feats, f_prod))


# ======================================================================================================= bagian
def _verdict(stats, meta):
    cnt = stats["cnt"]
    n_c, n_s = stats["n_cand"], stats["n_strand"]
    dup = cnt.get(C.DUPLIKAT, 0) + cnt.get(C.SERPIHAN, 0)
    trim = cnt.get(C.DIPANGKAS, 0)
    if meta["qc_only"]:
        head = ("%s dari %s garis menumpuk dengan garis lain." % (_n(dup + trim), _n(n_c))) if dup + trim else \
            "Tidak ada garis yang menumpuk pada %s garis." % _n(n_c)
        sub = ("Pemeriksaan saja: tidak ada hasil baru yang dibuat. %s garis akan dibuang sebagai duplikat dan %s "
               "dipangkas bila dikonsolidasikan." % (_n(dup), _n(trim)))
    else:
        head = "%s garis menjadi %s garis tanpa tumpukan." % (_n(n_c), _n(stats.get("n_kabel", 0)))
        saved = stats["len_in"] - stats["len_out"]
        sub = ("Di setiap jalur hanya %s yang dipertahankan, lengkap dengan atribut aslinya. Panjang total %s "
               "menjadi %s%s." % ("garis terpanjang" if meta.get("nodate") else "garis tertua", _km(stats["len_in"]),
                                  _km(stats["len_out"]),
                                  (" (tumpukan %s dibuang)" % _km(saved)) if saved > 0 else ""))
    return head, sub


def _health(stats, meta):
    """Daftar 'siap dipakai?': (level ok/warn/info, judul, penjelasan, tautan)."""
    cnt = stats["cnt"]
    dup = cnt.get(C.DUPLIKAT, 0) + cnt.get(C.SERPIHAN, 0)
    trim = cnt.get(C.DIPANGKAS, 0)
    out = []
    if meta["qc_only"]:
        out.append(("info" if dup + trim else "ok", "Garis menumpuk",
                    "%s duplikat, %s sejajar sebagian. Jalankan Consolidate Lines untuk membereskannya." % (
                        _n(dup), _n(trim)) if dup + trim else "Tidak ditemukan tumpukan.", "#garis"))
    else:
        out.append(("ok", "Tumpukan dibereskan",
                    "%s duplikat dibuang, %s garis dipangkas di bagian sejajar." % (_n(dup), _n(trim)), "#garis"))
    if meta.get("nodate"):
        out.append(("warn", "Tanpa tanggal pembuatan",
                    "Garis tertua tidak bisa ditentukan; yang dipertahankan garis terpanjang (su_dasar = PANJANG). "
                    "Minta data yang memuat CREATEDATE bila ada.", "#umur"))
    elif stats.get("n_bad_date"):
        out.append(("info", "Sebagian tanggal kosong",
                    "%s garis tanggalnya kosong atau tidak masuk akal (#N/A, 1900, masa depan); diletakkan di urutan "
                    "terakhir." % _n(stats["n_bad_date"]), "#umur"))
    else:
        out.append(("ok", "Tanggal pembuatan terbaca", "Semua garis punya tanggal; garis tertua menang.", "#umur"))
    if stats.get("n_gap"):
        out.append(("warn", "Celah perlu dicek",
                    "%s ujung berhenti dekat jalur lain. Periksa di peta lalu centang yang sudah dicek." %
                    _n(stats["n_gap"]), "#celah"))
    else:
        out.append(("ok", "Tidak ada celah", "Tidak ada ujung yang berhenti dekat jalur lain.", "#celah"))
    rd = stats.get("road") or {}
    if rd.get("mode") in ("osm", "layer") and not rd.get("n_roads"):
        out.append(("warn", "Jalan tidak ditemukan", "Tidak ada ruas jalan yang termuat di sekitar data (%s). Hanya "
                    "koridor jarak yang dipakai; jalankan ulang saat internet stabil." % (rd.get("note") or "-"),
                    "#teknis"))
    elif rd.get("mode") in ("osm", "layer"):
        src = "OpenStreetMap" if rd["mode"] == "osm" else "layer jalan %s" % rd.get("source", "")
        out.append(("ok", "Dicocokkan ke jalan", "%s garis (%s) mengikuti jalan yang sama dengan garis di sisi lain jalan "
                    "dan dijadikan satu jalur. Acuan: %s, %s ruas jalan." % (
                        _n(rd.get("n_lines", 0)), _km(rd.get("merged_m", 0)), src, _n(rd.get("n_roads", 0))), "#garis"))
    elif rd.get("mode") == "failed":
        out.append(("warn", "Pencocokan jalan tidak berjalan", "Data jalan tidak dapat dimuat (%s). Hanya koridor jarak "
                    "yang dipakai; garis di dua sisi jalan lebar bisa tetap tampil dua." % rd.get("note", "-"),
                    "#teknis"))
    warns = [m for lvl, m in stats.get("checks") or [] if lvl == "W"]
    if warns:
        out.append(("warn", "Toleransi perlu ditinjau", warns[0], "#profil"))
    elif stats.get("profile"):
        info = [m for lvl, m in stats.get("checks") or [] if lvl != "W"]
        out.append(("ok", "Lebar koridor %s m" % _n(2 * meta["tol"], 0), info[0] if info else
                    "Jarak antar-garis data Anda sesuai toleransi %s m." % _n(meta["tol"], 1), "#profil"))
    if stats.get("n_frag") and not meta["qc_only"]:
        out.append(("info", "Fragmen pendek", "%s untai di bawah %s m (total %s) ditandai terpisah." % (
            _n(stats["n_frag"]), _n(meta.get("frag_min", 25)), _km(stats.get("len_frag", 0))), "#untai"))
    return out


def _health_html(items):
    ico = {"ok": "&#10003;", "warn": "!", "info": "i"}
    return "".join(
        "<li class='h-%s'><span class='hi' aria-hidden='true'>%s</span><div><b>%s</b><p>%s</p></div>"
        "<a href='%s' class='hl'>Lihat</a></li>" % (lv, ico[lv], E(t), E(d), a) for lv, t, d, a in items)


def _donut(cnt, total):
    r, c = 52.0, 2 * math.pi * 52.0
    off, segs = 0.0, []
    for k, lab, col, _d in STATUS:
        v = cnt.get(k, 0)
        if not v:
            continue
        ln = c * v / max(total, 1)
        segs.append("<circle r='52' cx='70' cy='70' fill='none' stroke='%s' stroke-width='22' stroke-dasharray="
                    "'%.2f %.2f' stroke-dashoffset='%.2f' transform='rotate(-90 70 70)'><title>%s: %s</title>"
                    "</circle>" % (col, ln, c - ln, -off, E(lab), _n(v)))
        off += ln
    return ("<svg viewBox='0 0 140 140' class='donut' role='img' aria-label='Komposisi keputusan'>%s"
            "<text x='70' y='66' text-anchor='middle' class='dn'>%s</text><text x='70' y='86' text-anchor='middle' "
            "class='dl'>garis diperiksa</text></svg>" % ("".join(segs), _n(total)))


def _kpis(stats, meta):
    cnt = stats["cnt"]
    dup = cnt.get(C.DUPLIKAT, 0) + cnt.get(C.SERPIHAN, 0)
    k = [("Garis diperiksa", stats["n_cand"], "", "Garis yang lolos saringan produk/LOB.")]
    if not meta["qc_only"]:
        k.append(("Kabel tunggal", stats.get("n_kabel", 0), "good", "Satu garis per jalur di berkas hasil."))
    k += [("Duplikat dibuang", dup, "bad", "Garis yang sebagian besar menumpuk dengan garis yang lebih diutamakan."),
          ("Dipangkas", cnt.get(C.DIPANGKAS, 0), "mid", "Garis yang sebagian sejajar; bagian uniknya dipakai."),
          ("Celah perlu dicek", stats.get("n_gap", 0), "warn" if stats.get("n_gap") else "",
           "Ujung yang berhenti dekat jalur lain.")]
    cards = "".join(
        "<div class='kpi %s' title='%s'><b data-count='%d'>%s</b><span>%s</span></div>" % (
            cls, E(tip), v, _n(v), E(lab)) for lab, v, cls, tip in k)
    if not meta["qc_only"]:
        li, lo = stats["len_in"], stats["len_out"]
        pct = 100.0 * lo / li if li > 0 else 0
        cards += ("<div class='kpi wide'><span>Panjang jaringan</span><div class='lenbar'><i style='width:100%%'>"
                  "</i><em>sebelum %s</em></div><div class='lenbar after'><i style='width:%.1f%%'></i><em>sesudah %s"
                  "</em></div></div>" % (_km(li), pct, _km(lo)))
    return cards


def _oldest_html(stats, meta):
    rows = stats.get("oldest") or []
    if meta.get("nodate"):
        return ("<div class='callout warn'><b>Data ini tidak punya tanggal pembuatan.</b> Karena umur garis tidak "
                "bisa dibandingkan, di setiap %s Seuntai mempertahankan garis terpanjang. Semua hasil ditandai "
                "%s = PANJANG dan nama berkasnya memuat _TANPA_TANGGAL. Bila tersedia data yang memuat CREATEDATE, "
                "jalankan ulang untuk mendapatkan garis tertua.</div>" % (T("koridor", "koridor"), T("dasar", "su_dasar")))
    if not rows:
        return ""
    nm = "Nama kabel (%s)" % meta["f_id"] if meta.get("f_id") else "Nama kabel"
    body = "".join(
        "<tr data-z='G:%s' tabindex='0'><td class='nw'>%s</td><td><b>%s</b></td><td>%s</td><td class='r nw'>%s</td>"
        "<td>%s</td><td>%s</td><td class='mono'>%s</td></tr>" % (
            E(str(r["fid"])), E(r["tanggal"]), E(r["nama"] or "-"), E(r["produk"] or "-"), _km(r["panjang"]),
            E({"DIPAKAI": "Dipakai utuh", "DIPANGKAS": "Dipangkas"}.get(r["status"], r["status"])),
            E(r["untai"] or "-"), E(str(r["fid"]))) for r in rows)
    first = rows[0]
    return ("<h3>10 kabel tertua yang dipertahankan</h3><p class='lead'>Kabel paling awal: <b>%s</b>, dibuat %s. "
            "Klik baris untuk melihat kabel di peta beserta ceritanya.</p><div class='tw'><table><thead><tr>"
            "<th>Tanggal dibuat</th><th>%s</th><th>Produk</th><th class='r'>Panjang</th><th>Status</th><th>Untai</th>"
            "<th>FID QGIS</th></tr></thead><tbody>%s</tbody></table></div>" % (
                E(first["nama"] or ("FID %s" % first["fid"])), E(first["tanggal"]), E(nm), body))


def _profile_html(stats, meta):
    """Grafik distribusi jarak ke garis lain terdekat + penilaian toleransi, dengan penjelasan sederhana."""
    pr = stats.get("profile")
    checks = stats.get("checks") or []
    if not pr:
        return ""
    W, H, L, B, Tp, Rr = 760, 260, 46, 34, 14, 46
    bins, cum, w = pr["bins"], pr["cum"], pr["bin_w"]
    mx = max(bins) or 1.0
    n = len(bins)
    bw = (W - L - Rr) / float(n)

    def X(d):
        return L + (W - L - Rr) * d / pr["max_d"]

    def Y(v, top):
        return Tp + (H - Tp - B) * (1 - v / top)
    parts = []
    for i in range(0, 101, 25):
        y = Y(i, 100.0)
        parts.append("<line x1='%d' x2='%d' y1='%.1f' y2='%.1f' class='gl'/>" % (L, W - Rr, y, y))
        parts.append("<text x='%d' y='%.1f' class='ax' text-anchor='start'>%d%%</text>" % (W - Rr + 6, y + 4, i))
    for i, v in enumerate(bins):
        x = L + i * bw
        y = Y(v, mx)
        parts.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' class='hb'><title>%s-%s m: %s%% panjang"
                     "</title></rect>" % (x + 1, y, max(bw - 2, 0.5), H - B - y, _n(i * w, 1), _n((i + 1) * w, 1),
                                          _n(v, 1)))
    pts = " ".join("%.1f,%.1f" % (L + (i + 1) * bw, Y(c, 100.0)) for i, c in enumerate(cum))
    parts.append("<polyline points='%.1f,%.1f %s' class='cum'/>" % (L, Y(0, 100.0), pts))
    for d in range(0, int(pr["max_d"]) + 1, 1 if pr["max_d"] <= 12 else 2):
        parts.append("<text x='%.1f' y='%d' class='ax' text-anchor='middle'>%d</text>" % (X(d), H - B + 16, d))
    parts.append("<text x='%.1f' y='%d' class='ax' text-anchor='middle'>jarak ke garis lain terdekat (m)</text>"
                 % ((L + W - Rr) / 2.0, H - 4))
    parts.append("<text x='%d' y='%.1f' class='ax' text-anchor='end'>%s%%</text>" % (L - 6, Y(mx, mx) + 4, _n(mx, 0)))
    marks = [(meta["tol"], "tol", "toleransi %s m" % _n(meta["tol"], 2))]
    if pr.get("knee") is not None:
        marks.append((pr["knee"], "knee", "lutut %s m" % _n(pr["knee"], 1)))
    marks.append((5.5, "road", "separuh RUMIJA jalan kecil 5,5 m"))
    for k, (d, cls, lab) in enumerate(marks):
        if d <= pr["max_d"]:
            parts.append("<line x1='%.1f' x2='%.1f' y1='%d' y2='%d' class='mk %s'/>" % (X(d), X(d), Tp, H - B, cls))
            parts.append("<text x='%.1f' y='%d' class='mt %s'>%s</text>" % (X(d) + 4, Tp + 12 + 14 * k, cls, lab))
    svg = ("<svg viewBox='0 0 %d %d' role='img' aria-label='Distribusi jarak antar-garis'>%s</svg>"
           % (W, H, "".join(parts)))
    share = C.cum_at(pr, meta["tol"]) or 0.0
    lis = "".join("<li class='%s'>%s</li>" % ("w" if lvl == "W" else "i", E(msg)) for lvl, msg in checks)
    return ("<section id='profil' aria-labelledby='h-prof'><h2 id='h-prof'>Kualitas data: apakah toleransinya "
            "cocok?</h2><div class='explain'><p><b>Cara membaca grafik.</b> Seuntai mengambil titik setiap %s m di "
            "sepanjang garis dan mengukur jaraknya ke garis lain yang terdekat. Batang ungu = persen panjang pada "
            "jarak itu, garis gelap = jumlah kumulatif.</p><ul><li>Batang tinggi di <b>kiri</b> (jarak kecil) = "
            "banyak garis menumpuk: inilah yang dibereskan.</li><li>Garis merah = %s yang dipakai: garis yang "
            "berjarak di kiri garis merah dijadikan satu, yang di kanannya dianggap jalur lain. Garis merah sebaiknya "
            "berada di kanan %s (garis biru putus-putus). Garis abu-abu = separuh %s jalan kecil.</li></ul></div>"
            "<div class='chart'>%s</div><ul class='checks'>%s</ul><p class='mut small'>Dalam toleransi %s m: %s%% "
            "panjang garis punya pasangan sejajar. Tanpa garis lain dalam %s m: %s%%.</p></section>" % (
                _n(pr["step"], 1), T("toleransi", "toleransi"), T("lutut", "lutut kurva"), T("rumija", "RUMIJA"), svg, lis, _n(meta["tol"], 2),
                _n(share, 1), _n(pr["max_d"], 0), _n(pr["none"], 1)))


def _params_html(p, meta, stats):
    filt = []
    if meta["f_prod"]:
        filt.append("%s = %s" % (meta["f_prod"], ", ".join(meta["values"])))
    if meta["expr"]:
        filt.append(meta["expr"])
    params = [
        ("Layer", meta["layer"]), ("Filter", " dan ".join(filt) or "tanpa filter (semua garis)"),
        ("Dibuang oleh filter", "%s (produk) + %s (ekspresi)" % (_n(stats["n_out_prod"]), _n(stats["n_out_expr"]))),
        ("Kolom tanggal", meta["f_tgl"] or "tidak ada"), ("Prioritas", meta["prior"]),
        ("Format tanggal D/M/Y", "hari/bulan/tahun" if meta["dayfirst"] else "bulan/hari/tahun"),
        ("Kolom grup", meta["f_grp"] or "tidak dipakai"), ("Cara konsolidasi", meta["mode"]),
        ("Lebar koridor", "%s m (toleransi %s m ke kiri dan kanan)" % (_n(2 * meta["tol"], 1), _n(meta["tol"], 2))), ("Ambang duplikat", "%s%% panjang" % _n(meta["cover"], 0)),
        ("Pencocokan ke jalan", meta.get("road_mode") or "-"),
        ("Toleransi sambung ujung", "%s m" % _n(meta["snap"], 2)),
        ("Kolom identitas kabel", meta.get("f_id") or "tidak dipakai"),
        ("Sambung celah segaris / berkabel sama", ("sampai %s m" % _n(meta.get("smart", 0), 1))
         if meta.get("smart") else "tidak"),
        ("Jembatani semua celah", ("sampai %s m" % _n(meta["gap"], 2)) if meta["gap"] else "tidak"),
        ("Batas fragmen", "untai < %s m" % _n(meta.get("frag_min", 25), 0)),
        ("Pita drift", "%s m (sejajar dalam pita ini = koridor yang sama)" % _n(meta.get("drift") or 0, 1)),
        ("Radius pelaporan celah", "%s m" % _n(meta["gap_report"], 1)), ("Bentuk keluaran", meta["keluaran"]),
        ("CRS layer / CRS hitung", "%s / %s%s" % (meta["crs"], meta["work_crs"],
                                                  (" (%s)" % stats["crs_why"]) if stats.get("crs_why") else "")),
        ("Panjang", "elipsoidal (meter di permukaan bumi), dihitung QgsDistanceArea"),
        ("Shapefile", ", ".join(os.path.basename(x) for x in stats.get("shp") or []) or "tidak diminta"),
        ("Alat", "%s, Seuntai %s" % (meta["alg"], meta["version"])), ("Waktu jalan", "%s (%s detik)" % (
            meta["run"], _n(stats["elapsed"], 1))),
    ]
    if p.get("stride", 1) > 1:
        params.append(("Penyederhanaan peta", "1 dari %d verteks ditampilkan (data dan layer tidak berubah)" %
                       p["stride"]))
    out = "".join("<tr><th scope='row'>%s</th><td>%s</td></tr>" % (E(a), E(str(b))) for a, b in params)
    if stats.get("prod_seen"):
        top = sorted(stats["prod_seen"].items(), key=lambda kv: -kv[1])[:10]
        out += "<tr><th scope='row'>Nilai produk di data</th><td>%s</td></tr>" % E(
            ", ".join("%s (%d)" % (k or "<kosong>", v) for k, v in top))
    return out


# ======================================================================================================= render
def render(path, p):
    meta, stats, data = p["meta"], p["stats"], p["data"]
    cnt = stats["cnt"]
    qc = bool(meta["qc_only"])
    head, sub = _verdict(stats, meta)
    legend = "".join(
        "<li><svg width='34' height='10' aria-hidden='true'><line x1='2' y1='5' x2='32' y2='5' stroke='%s' "
        "stroke-width='4' stroke-linecap='round' stroke-dasharray='%s'/></svg><span>%s</span><b>%s</b>"
        "<em>%s%%</em></li>" % (col, dash, T(k.lower(), lab) if k.lower() in GLOSS_KEYS else E(lab),
                                _n(cnt.get(k, 0)), _n(100.0 * cnt.get(k, 0) / max(stats["n_cand"], 1), 0))
        for k, lab, col, dash in STATUS if cnt.get(k, 0) or k in ("DIPAKAI", "DIPANGKAS", "DUPLIKAT"))
    kep = "".join(
        "<tr><td><b>%s</b><br><span class='mut'>%s</span></td><td>%s</td><td class='nw'>%s</td>"
        "<td><span class='tag t-%s'>%s</span></td></tr>" % (E(a), E(b), E(c), SB.ref_html(d), st.lower(), st.title())
        for a, b, c, d, st in SB.KEPUTUSAN)
    src = "".join("<li id='%s'><b>%s</b> %s%s</li>" % (i, i, E(t), (" <a href='%s' rel='noopener'>%s</a>" % (
        E(u), E(u.split("//")[-1].split("/")[0]))) if u else "") for i, t, u in SB.SUMBER)
    gloss = "".join("<div id='g-%s'><dt>%s</dt><dd>%s</dd></div>" % (k, E(t), E(d)) for k, t, d in GLOSS)
    faq = "".join("<details><summary>%s</summary><p>%s</p></details>" % (E(q), E(a)) for q, a in FAQ)

    cfg = {"tol": meta["tol"], "cover": meta["cover"], "nodate": bool(meta.get("nodate")), "qc": qc,
           "drift": meta.get("drift") or 0, "frag": meta.get("frag_min", 25), "f_id": meta.get("f_id") or "",
           "f_prod": meta.get("f_prod") or "", "layer": meta["layer"], "run": meta["run"],
           "n_cand": stats["n_cand"], "n_kabel": stats.get("n_kabel", 0),
           "n_dup": cnt.get(C.DUPLIKAT, 0) + cnt.get(C.SERPIHAN, 0), "n_trim": cnt.get(C.DIPANGKAS, 0),
           "n_used": cnt.get(C.DIPAKAI, 0)}
    js_data = {"S": data["S"], "G": data["G"], "N": data["N"], "st": [list(s) for s in STATUS],
               "nt": [list(n) for n in NOTE], "cfg": cfg, "gl": {k: [t, d] for k, t, d in GLOSS}}

    css_fonts = (_font("Seuntai Display", "display-800.woff", 800) + _font("Seuntai Text", "inter-400.woff", 400) +
                 _font("Seuntai Text", "inter-600.woff", 600) + _font("Seuntai Mono", "plexmono-400.woff", 400))
    leaflet_css = _read("assets", "map", "leaflet.css").decode("utf-8")
    leaflet_js = _read("assets", "map", "leaflet.js").decode("utf-8")
    nav = [("ringkasan", "Ringkasan"), ("peta", "Peta"), ("cara", "Cara kerja")]
    if not qc:
        nav.append(("umur", "Umur"))
        nav.append(("untai", "Untai"))
    nav += [("garis", "Per garis"), ("celah", "Celah")]
    if stats.get("profile"):
        nav.append(("profil", "Kualitas data"))
    nav += [("tanya", "Tanya jawab"), ("istilah", "Istilah"), ("teknis", "Teknis")]
    nav_html = "".join("<a href='#%s'>%s</a>" % (a, E(b)) for a, b in nav)
    views = [("dec", "Keputusan"), ("before", "Sebelum")]
    if not qc:
        views += [("after", "Sesudah"), ("cmp", "Bandingkan")]
    views_html = "".join("<button type='button' data-v='%s' aria-pressed='%s'>%s</button>" % (
        v, "true" if v == "dec" else "false", lab) for v, lab in views)

    doc = TEMPLATE.format(
        title=E("Seuntai - %s" % meta["layer"]), fonts=css_fonts, css=CSS, leaflet_css=leaflet_css, logo=_logo(),
        layer=E(meta["layer"]), run=E(meta["run"]), nav=nav_html,
        head=E(head), sub=E(sub), health=_health_html(_health(stats, meta)),
        kpis=_kpis(stats, meta), donut=_donut(cnt, stats["n_cand"]), legend=legend, views=views_html,
        t_koridor=T("koridor", "koridor"), t_toleransi=T("toleransi", "toleransi"), t_rumija=T("rumija", "RUMIJA"), t_prioritas=T("prioritas", "urutan prioritas"),
        t_duplikat=T("duplikat", "duplikat"), t_dipangkas=T("dipangkas", "dipangkas"),
        t_untai=T("untai", "untai"), t_celah=T("celah", "celah"), t_jembatan=T("jembatan", "jembatan"),
        t_fragmen=T("fragmen", "fragmen"), t_kabel=T("kabel", "kabel tunggal"),
        umur_sec="" if qc else UMUR_SECTION.format(oldest=_oldest_html(stats, meta), lead="" if meta.get("nodate") else UMUR_LEAD),
        untai_sec="" if qc else STRAND_SECTION.format(t_untai=T("untai", "untai"), t_fragmen=T("fragmen", "fragmen")),
        profile=_profile_html(stats, meta), faq=faq, gloss=gloss,
        params=_params_html(p, meta, stats), kep=kep, src=src, version=E(meta["version"]), author=E(meta["author"]),
        data=json.dumps(js_data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        leaflet_js=leaflet_js, js=JS,
        attrib=(" Data jalan &copy; <a href='https://www.openstreetmap.org/copyright' rel='noopener'>OpenStreetMap "
                "contributors</a> (ODbL)." if (stats.get("road") or {}).get("mode") == "osm" else ""))
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


UMUR_LEAD = ("<p class='lead'>Jumlah garis menurut tahun pembuatan. Hijau = dipertahankan, merah = dibuang karena "
             "menumpuk dengan garis yang lebih tua. Biasanya garis yang lebih baru lebih banyak dibuang, karena merupakan "
             "salinan dari jalur lama.</p>")

UMUR_SECTION = """
<section id="umur" aria-labelledby="h-umur">
  <h2 id="h-umur">Umur jaringan</h2>
  {lead}
  <div id="yearchart" class="chart"></div>
  {oldest}
</section>"""

STRAND_SECTION = """
<section id="untai" aria-labelledby="h-untai">
  <h2 id="h-untai">Untai hasil</h2>
  <p class="lead">Satu baris per {t_untai} (jaringan yang tersambung). "Utuh" berarti satu garis tanpa cabang.
  {t_fragmen} adalah untai yang sangat pendek. Klik baris untuk melihatnya di peta.</p>
  <div class="filters"><label class="chk"><input type="checkbox" id="hidefrag" checked> Sembunyikan fragmen</label>
  <span id="cntu" class="mut"></span></div>
  <div class="tw"><table id="t-untai"><thead><tr><th>Untai</th><th>Kelas</th><th>Grup</th><th class="r">Panjang</th>
  <th class="r">Garis sumber</th><th class="r">Ruas</th><th class="r">Cabang</th><th class="r">Ujung</th><th>Utuh</th>
  <th>Tanggal tertua</th><th class="r">Jembatan</th></tr></thead><tbody></tbody></table></div>
</section>"""

TEMPLATE = """<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{fonts}{leaflet_css}{css}</style></head>
<body>
<a class="skip" href="#ringkasan">Langsung ke isi</a>
<header class="top">
  <div class="brand">{logo}<div><b>Seuntai</b><span>Banyak garis, seuntai jalur</span></div></div>
  <div class="meta"><span>{layer}</span><span>{run}</span></div>
  <div class="actions"><button class="btn primary" id="tourbtn" type="button">Tur singkat</button>
  <button class="btn" type="button" onclick="window.print()">Cetak / PDF</button></div>
  <nav class="tabs" aria-label="Bagian laporan">{nav}</nav>
</header>
<main>
<section id="ringkasan" class="hero" aria-labelledby="h-verdict">
  <div class="verdict">
    <p class="eyebrow">Hasil dalam satu kalimat</p>
    <h1 id="h-verdict">{head}</h1>
    <p class="sub">{sub}</p>
    <h2 class="mini">Siap dipakai?</h2>
    <ul class="health">{health}</ul>
  </div>
  <div class="side">
    <div class="kpis">{kpis}</div>
    <div class="mix"><div class="dwrap">{donut}</div><ul class="legend">{legend}</ul></div>
  </div>
</section>

<section id="peta" aria-labelledby="h-peta">
  <div class="sechead"><h2 id="h-peta">Peta interaktif</h2>
  <div class="seg" role="group" aria-label="Tampilan peta">{views}</div></div>
  <p class="lead" id="viewhelp"></p>
  <div class="mapwrap" id="mapwrap">
    <div id="map" aria-label="Peta interaktif garis dan untai"></div>
    <div class="mapsearch"><input id="msearch" type="search" placeholder="Cari FID atau nama kabel" aria-label="Cari garis"
      autocomplete="off"><ul id="mresults" role="listbox"></ul></div>
    <div class="maptools" role="group" aria-label="Lapisan tambahan">
      <label><input type="checkbox" data-l="NC"> Celah</label>
      <label><input type="checkbox" data-l="NJ"> Jembatan</label>
      <label><input type="checkbox" data-l="NB"> Cabang &amp; ujung</label>
      <label><input type="checkbox" id="osm"> Peta jalan (online)</label>
      <button type="button" id="fsbtn" class="mbtn" aria-label="Layar penuh">&#x26F6;</button>
    </div>
    <div class="cmpui" id="cmpui" hidden><span class="cl">Sebelum</span><span class="cr">Sesudah</span>
      <div class="divider" id="divider"></div>
      <input type="range" id="cmprange" min="5" max="95" value="50" aria-label="Geser pembanding"></div>
    <div class="mlegend" id="mlegend"></div>
  </div>
  <p class="mut small">Klik garis di peta untuk membaca ceritanya: mengapa garis itu dipakai, dipangkas, atau dibuang.</p>
</section>

<section id="cara" aria-labelledby="h-cara">
  <h2 id="h-cara">Cara Seuntai bekerja</h2>
  <p class="lead">Contoh tiga garis di satu jalan. Tekan <b>Putar</b> atau pilih langkah.</p>
  <div class="explainer">
    <svg id="exsvg" class="ex s1" viewBox="0 0 640 270" role="img" aria-label="Animasi langkah konsolidasi">
      <rect x="0" y="0" width="640" height="270" rx="16" class="exbg"/>
      <path d="M20 200 C200 190 380 210 620 200" class="road"/>
      <path d="M40 200 C200 190 380 210 600 200" class="corr"/>
      <path d="M40 200 C200 190 380 210 600 200" class="ln lA"/>
      <path d="M60 195 C200 185 380 205 580 195" class="ln lB"/>
      <path d="M40 206 C150 202 250 208 330 206" class="ln lCp"/>
      <path d="M330 206 C420 200 500 130 600 60" class="ln lCu"/>
      <g class="bd b1"><rect x="40" y="226" width="104" height="24" rx="12"/><text x="92" y="242" text-anchor="middle" id="bA">A · 2019</text></g>
      <g class="bd b2"><rect x="40" y="148" width="104" height="24" rx="12"/><text x="92" y="164" text-anchor="middle" id="bB">B · 2021</text></g>
      <g class="bd b3"><rect x="470" y="46" width="104" height="24" rx="12"/><text x="522" y="62" text-anchor="middle" id="bC">C · 2023</text></g>
      <g class="tag2 tB"><text x="156" y="165">B: 96% di dalam koridor A, dibuang</text></g>
      <g class="tag2 tC"><text x="156" y="243">C: bagian sejajar dipangkas, belokan tetap dipakai</text></g>
    </svg>
    <div class="exside">
      <ol id="exsteps" class="steps"></ol>
      <div class="excap" id="excap" aria-live="polite"></div>
      <div class="exbtns"><button class="btn" type="button" id="exprev">&larr; Sebelumnya</button>
      <button class="btn primary" type="button" id="explay">Putar</button>
      <button class="btn" type="button" id="exnext">Berikutnya &rarr;</button></div>
    </div>
  </div>
  <div class="rules">
    <div><b>1. Urutkan</b><p>Setiap garis diberi {t_prioritas}: tanggal pembuatan paling tua di depan.</p></div>
    <div><b>2. Bandingkan</b><p>Garis diperiksa satu per satu terhadap {t_koridor} garis yang sudah dipakai (lebar mengacu {t_rumija}).</p></div>
    <div><b>3. Putuskan</b><p>Hampir semua di dalam koridor = {t_duplikat}; sebagian = {t_dipangkas}; lainnya dipakai utuh.</p></div>
    <div><b>4. Sambungkan</b><p>Potongan yang dipakai digabung menjadi {t_untai}; {t_celah} kecil yang jelas segaris jadi {t_jembatan}.</p></div>
    <div><b>5. Simpan</b><p>Hasil utama: {t_kabel} dengan atribut asli, plus laporan ini. Data asli tidak berubah.</p></div>
  </div>
</section>
{umur_sec}
{untai_sec}
<section id="garis" aria-labelledby="h-garis">
  <h2 id="h-garis">Keputusan per garis</h2>
  <p class="lead">Semua garis yang diperiksa, urut prioritas (baris atas menang bila jalurnya sama). Klik baris untuk
  membaca ceritanya dan melihatnya di peta.</p>
  <div class="filters"><div class="chips" id="chips" role="group" aria-label="Saring status"></div>
  <input id="q" type="search" placeholder="Cari FID, nama kabel, untai, alasan" aria-label="Cari">
  <button class="btn" type="button" id="csvg">Unduh CSV</button><span id="cnt" class="mut"></span></div>
  <div class="tw"><table id="t-garis"><thead><tr><th class="r">Urutan</th><th>FID</th><th>Nama</th><th>Status</th>
  <th>Tanggal</th><th class="r">Panjang</th><th class="r">Dipakai</th><th class="r">Menumpuk</th>
  <th>Kalah dari</th><th>Untai</th></tr></thead><tbody></tbody></table></div>
  <p class="mut small" id="more"></p>
</section>

<section id="celah" aria-labelledby="h-celah">
  <h2 id="h-celah">Celah: daftar periksa</h2>
  <p class="lead">Celah adalah ujung jalur yang berhenti dekat jalur lain dan mengarah ke sana. Klik baris untuk
  melompat ke lokasinya, lalu centang bila sudah dicek. Centang tersimpan di peramban ini dan ikut di CSV.</p>
  <div class="progress"><div class="pbar"><i id="pfill"></i></div><span id="ptext"></span>
  <button class="btn" type="button" id="csvc">Unduh CSV celah</button></div>
  <div class="tw"><table id="t-cat"><thead><tr><th>Dicek</th><th>Jenis</th><th>Untai</th><th class="r">Jarak</th>
  <th>Keterangan</th><th>Koordinat</th></tr></thead><tbody></tbody></table></div>
</section>
{profile}
<section id="tanya" aria-labelledby="h-tanya">
  <h2 id="h-tanya">Tanya jawab</h2>
  <div class="faq">{faq}</div>
</section>

<section id="istilah" aria-labelledby="h-ist">
  <h2 id="h-ist">Kamus istilah</h2>
  <p class="lead">Istilah bergaris titik-titik di laporan ini bisa disentuh atau diarahkan kursor untuk penjelasan singkat.</p>
  <input id="gq" type="search" class="gsearch" placeholder="Cari istilah" aria-label="Cari istilah">
  <dl class="gloss" id="gloss">{gloss}</dl>
</section>

<section id="teknis" aria-labelledby="h-tek">
  <h2 id="h-tek">Rincian teknis</h2>
  <details><summary>Parameter dan jejak proses</summary><div class="tw"><table class="kv">{params}</table></div></details>
  <details><summary>Dasar setiap keputusan dan sumbernya</summary>
  <p class="lead">Standar = mengikuti aturan resmi; literatur = metode dari publikasi atau dokumentasi rujukan; desain =
  nilai rekayasa yang diturunkan dari sumber, diuji, dan boleh diubah sesuai kondisi lapangan.</p>
  <div class="tw"><table class="kep"><thead><tr><th>Keputusan</th><th>Alasan</th><th>Sumber</th><th>Jenis</th>
  </tr></thead><tbody>{kep}</tbody></table></div>
  <h3>Sumber</h3><ol class="src">{src}</ol></details>
</section>
</main>

<aside id="story" class="story" aria-labelledby="sttitle" hidden>
  <button type="button" class="x" id="stclose" aria-label="Tutup">&times;</button>
  <p class="eyebrow">Cerita garis</p><h3 id="sttitle"></h3><div id="stbody"></div>
</aside>
<div id="tip" class="tip" role="tooltip" hidden></div>
<div id="tour" class="tour" hidden><div class="spot" id="tspot"></div><div class="tcard" id="tcard" role="dialog"
  aria-live="polite"><p class="eyebrow" id="tstep"></p><h3 id="ttitle"></h3><p id="ttext"></p>
  <div class="exbtns"><button class="btn" type="button" id="tskip">Tutup</button>
  <button class="btn primary" type="button" id="tnext">Lanjut</button></div></div></div>

<footer>Seuntai&trade; {version} &copy; 2026 {author}. GNU GPL v2 atau lebih baru. Hasil alat membantu, bukan
menggantikan, penilaian perancang dan pemeriksa.{attrib}</footer>
<script>{leaflet_js}</script>
<script>window.SEUNTAI={data};</script>
<script>{js}</script>
</body></html>"""

CSS = r"""
:root{--paper:#F6F4FA;--card:#FFFFFF;--ink:#1A1033;--mut:#5A5470;--line:#E2DDEE;--plum:#2A1650;--lilac:#A898FF;
--coral:#FF4D6D;--amber:#FFB703;--focus:#0072B2;--hl:#FFF3CC;--ok:#007A5A;--okbg:#E3F6EF;--warn:#B54708;
--warnbg:#FFF1E0;--info:#0060A0;--infobg:#E6F1FA;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--paper:#130B26;--card:#1C1236;--ink:#EEEAF8;--mut:#B3ABCB;--line:#342857;
--hl:#3A2E10;--ok:#4FD6A8;--okbg:#123528;--warn:#FFB26B;--warnbg:#3A2412;--info:#7CC3F5;--infobg:#132B40;
color-scheme:dark}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:120px}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 'Seuntai Text',system-ui,sans-serif;
font-feature-settings:'tnum' 1}
a{color:inherit;text-decoration-color:var(--coral);text-underline-offset:2px}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.skip{position:absolute;left:-999px;top:0}.skip:focus{left:12px;top:12px;z-index:3000;background:var(--card);padding:8px}
.top{position:sticky;top:0;z-index:1500;display:flex;align-items:center;gap:8px 20px;padding:12px 28px 0;
border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--card) 92%,transparent);backdrop-filter:blur(8px);
flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px}
.brand b{display:block;font:800 21px/1 'Seuntai Display',sans-serif;letter-spacing:-.02em}
.brand span{font-size:12.5px;color:var(--mut)}
.top .meta{display:flex;gap:16px;flex-wrap:wrap;color:var(--mut);font-size:13px;margin-left:auto}
.top .meta span:first-child{color:var(--ink);font-weight:600}
.actions{display:flex;gap:8px}
.tabs{flex-basis:100%;display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;margin-top:4px}
.tabs a{padding:9px 12px;font-size:13.5px;font-weight:600;color:var(--mut);text-decoration:none;white-space:nowrap;
border-bottom:3px solid transparent}
.tabs a.on{color:var(--ink);border-bottom-color:var(--coral)}
.btn{font:600 13px 'Seuntai Text',sans-serif;border:1px solid var(--line);background:var(--card);color:var(--ink);
border-radius:999px;padding:7px 14px;cursor:pointer}
.btn.primary{background:var(--ink);color:var(--card);border-color:var(--ink)}
main{max-width:1320px;margin:0 auto;padding:0 28px 48px}
section{padding:30px 0 10px;border-top:1px solid var(--line)}
.hero{display:grid;grid-template-columns:1.1fr 1fr;gap:32px;border-top:0;padding-top:26px}
.eyebrow{margin:0 0 6px;font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--coral)}
h1{font:800 clamp(30px,4vw,44px)/1.06 'Seuntai Display',sans-serif;letter-spacing:-.03em;margin:0 0 12px;text-wrap:balance}
.sub{font-size:17px;margin:0 0 20px;max-width:52ch}
h2{font:800 26px/1.15 'Seuntai Display',sans-serif;letter-spacing:-.02em;margin:0 0 8px}
h2.mini{font-size:18px;margin:0 0 10px}
h3{font:800 18px 'Seuntai Display',sans-serif;margin:22px 0 8px}
.lead{margin:0 0 14px;color:var(--mut);max-width:80ch}
.health{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.health li{display:grid;grid-template-columns:30px 1fr auto;gap:12px;align-items:start;padding:11px 14px;border-radius:12px;
border:1px solid var(--line);background:var(--card)}
.health .hi{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;font-weight:800;font-size:14px}
.h-ok .hi{background:var(--okbg);color:var(--ok)}.h-warn .hi{background:var(--warnbg);color:var(--warn)}
.h-info .hi{background:var(--infobg);color:var(--info)}
.h-warn{border-color:color-mix(in srgb,var(--warn) 40%,var(--line))!important}
.health b{font-size:14.5px}.health p{margin:2px 0 0;color:var(--mut);font-size:13.5px}
.health .hl{font-size:13px;font-weight:600;align-self:center}
.side{display:flex;flex-direction:column;gap:16px}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.kpi b{display:block;font:800 28px/1.1 'Seuntai Display',sans-serif;letter-spacing:-.02em}
.kpi span{font-size:12.5px;color:var(--mut)}
.kpi.good b{color:var(--ok)}.kpi.bad b{color:#C2410C}.kpi.mid b{color:#B36B00}.kpi.warn b{color:var(--warn)}
.kpi.wide{grid-column:1/-1}
.lenbar{position:relative;height:24px;margin-top:8px;background:var(--paper);border-radius:8px;overflow:hidden}
.lenbar i{position:absolute;inset:0 auto 0 0;background:#B9B2CF;border-radius:8px;transition:width 1s}
.lenbar.after i{background:var(--coral)}
.lenbar em{position:relative;font-style:normal;font-size:12.5px;font-weight:600;padding:0 10px;line-height:24px;color:#1A1033}
.mix{display:grid;grid-template-columns:150px 1fr;gap:18px;align-items:center;background:var(--card);border:1px solid var(--line);
border-radius:14px;padding:14px}
.donut{width:150px;height:150px}.donut .dn{font:800 22px 'Seuntai Display',sans-serif;fill:var(--ink)}
.donut .dl{font-size:10px;fill:var(--mut)}
.legend{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.legend li{display:grid;grid-template-columns:38px 1fr auto 46px;align-items:center;gap:8px;font-size:14px}
.legend b{font-weight:600;text-align:right}.legend em{font-style:normal;color:var(--mut);text-align:right}
.sechead{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
.seg{display:inline-flex;background:var(--card);border:1px solid var(--line);border-radius:999px;padding:3px}
.seg button{font:600 13px 'Seuntai Text',sans-serif;border:0;background:none;color:var(--mut);padding:7px 14px;
border-radius:999px;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--ink);color:var(--card)}
.mapwrap{position:relative;height:clamp(420px,68vh,720px);border-radius:18px;overflow:hidden;border:1px solid var(--line);
background:#1A1033}
.mapwrap:fullscreen{height:100vh;border-radius:0}
#map{position:absolute;inset:0;background:radial-gradient(circle at 30% 20%,#2C1858,#140A2C 70%)}
.maptools{position:absolute;z-index:800;right:12px;top:12px;max-width:62%;display:flex;gap:6px;flex-wrap:wrap;
justify-content:flex-end}
.maptools label,.mbtn{background:rgba(20,10,44,.86);color:#EEEAF8;border-radius:999px;padding:5px 12px;font-size:12.5px;
cursor:pointer;border:0;font-family:inherit}
.maptools input{accent-color:#FFB703;margin:0 5px 0 0;vertical-align:-1px}
.mapsearch{position:absolute;z-index:810;left:56px;top:12px;width:min(320px,55%)}
.mapsearch input{width:100%;font:inherit;font-size:13.5px;padding:8px 12px;border-radius:999px;border:0;
background:rgba(255,255,255,.96);color:#1A1033;box-shadow:0 4px 18px rgba(0,0,0,.25)}
.mapsearch ul{list-style:none;margin:6px 0 0;padding:4px;background:#fff;color:#1A1033;border-radius:12px;
box-shadow:0 8px 24px rgba(0,0,0,.3);max-height:260px;overflow:auto}
.mapsearch ul:empty{display:none}
.mapsearch li{padding:7px 10px;border-radius:8px;cursor:pointer;font-size:13px}
.mapsearch li:hover,.mapsearch li[aria-selected=true]{background:#F1ECFF}
.mlegend{position:absolute;z-index:800;left:12px;bottom:28px;background:rgba(20,10,44,.86);color:#EEEAF8;
border-radius:12px;padding:8px 12px;font-size:12px;display:grid;gap:3px}
.mlegend i{display:inline-block;width:22px;height:4px;border-radius:2px;margin-right:7px;vertical-align:middle}
.cmpui .cl,.cmpui .cr{position:absolute;z-index:805;bottom:104px;background:rgba(20,10,44,.86);color:#fff;font-size:12px;
font-weight:600;padding:4px 10px;border-radius:999px}
.cmpui .cl{left:12px}.cmpui .cr{right:12px}
.divider{position:absolute;z-index:700;top:0;bottom:0;width:3px;background:#FFB703;box-shadow:0 0 0 1px rgba(0,0,0,.4);
pointer-events:none;left:50%}
#cmprange{position:absolute;z-index:806;left:5%;right:5%;bottom:70px;width:90%;accent-color:#FFB703}
.leaflet-pane.pclip{will-change:clip}
.leaflet-container{font:13px/1.45 'Seuntai Text',sans-serif;background:transparent}
.leaflet-popup-content-wrapper{border-radius:12px}
.leaflet-popup-content{margin:12px 14px;min-width:220px}
.pop h4{margin:0 0 6px;font:800 16px 'Seuntai Display',sans-serif}
.pop table{border-collapse:collapse;width:100%}.pop td{padding:2px 0;vertical-align:top;font-size:12.5px}
.pop td:first-child{color:#5A5470;padding-right:10px;white-space:nowrap}
.explainer{display:grid;grid-template-columns:1.4fr 1fr;gap:22px;align-items:start}
.ex{width:100%;height:auto;display:block;border-radius:16px}
.ex .exbg{fill:#1A1033}.ex .road{fill:none;stroke:#2E2150;stroke-width:46;stroke-linecap:round}
.ex .corr{fill:none;stroke:#009E73;stroke-width:30;stroke-linecap:round;opacity:0;transition:opacity .6s}
.ex .ln{fill:none;stroke:#B9B2CF;stroke-width:5;stroke-linecap:round;transition:all .7s}
.ex .bd{opacity:0;transition:opacity .5s}.ex .bd rect{fill:#FFFFFF}.ex .bd text{font:600 12px 'Seuntai Text',sans-serif;fill:#1A1033}
.ex .tag2{opacity:0;transition:opacity .5s}.ex .tag2 text{font:600 12.5px 'Seuntai Text',sans-serif;fill:#FFB703}
.ex.s2 .bd,.ex.s3 .bd,.ex.s4 .bd,.ex.s5 .bd{opacity:1}
.ex.s3 .corr,.ex.s4 .corr,.ex.s5 .corr{opacity:.28}
.ex.s3 .lA,.ex.s4 .lA,.ex.s5 .lA,.ex.s6 .lA{stroke:#009E73;stroke-width:6}
.ex.s4 .lB,.ex.s5 .lB{stroke:#D55E00;stroke-dasharray:4 9;opacity:.65}.ex.s4 .tB,.ex.s5 .tB{opacity:1}
.ex.s5 .lCp{stroke:#E69F00;stroke-dasharray:4 9;opacity:.5}.ex.s5 .lCu,.ex.s6 .lCu{stroke:#E69F00;stroke-width:6}
.ex.s5 .tC{opacity:1}
.ex.s6 .lB,.ex.s6 .lCp{opacity:0}
.exside{display:flex;flex-direction:column;gap:12px}
.steps{list-style:none;margin:0;padding:0;display:grid;gap:4px;counter-reset:s}
.steps li{counter-increment:s;padding:8px 12px;border-radius:10px;cursor:pointer;color:var(--mut);font-weight:600;font-size:14px}
.steps li::before{content:counter(s);display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;
background:var(--line);color:var(--ink);font-size:12px;margin-right:10px}
.steps li.on{background:var(--card);color:var(--ink);box-shadow:0 0 0 1px var(--line)}
.steps li.on::before{background:var(--coral);color:#fff}
.excap{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;min-height:96px}
.exbtns{display:flex;gap:8px;flex-wrap:wrap}
.rules{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:18px}
.rules div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.rules b{font-size:14px}.rules p{margin:4px 0 0;font-size:13.5px;color:var(--mut)}
.term{border-bottom:1.5px dotted var(--coral);cursor:help;color:inherit}
.tip{position:fixed;z-index:2500;max-width:320px;background:#1A1033;color:#EEEAF8;border-radius:12px;padding:10px 12px;
font-size:13px;line-height:1.5;box-shadow:0 10px 30px rgba(0,0,0,.35);pointer-events:none}
.tip b{display:block;color:#FFB703;margin-bottom:2px}
.callout{border-radius:12px;padding:12px 14px;margin:0 0 14px;border:1px solid var(--line);background:var(--card)}
.callout.warn{background:var(--warnbg);border-color:color-mix(in srgb,var(--warn) 45%,transparent)}
.explain{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:0 0 12px;max-width:90ch}
.explain p{margin:0 0 6px}.explain ul{margin:0;padding-left:20px}
.tw{overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--card);max-height:560px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:8px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
thead th{position:sticky;top:0;background:var(--card);font-weight:600;color:var(--mut);font-size:12.5px;z-index:1}
td.r,th.r{text-align:right}.nw{white-space:nowrap}
tbody tr[data-z]{cursor:pointer}tbody tr[data-z]:hover,tbody tr.sel{background:var(--hl)}
tr.done td{color:var(--mut)}tr.done td:nth-child(2){text-decoration:line-through}
.kv th{width:240px;color:var(--mut);font-weight:600}
.st{display:inline-flex;align-items:center;gap:6px;font-weight:600;white-space:nowrap}
.st i{display:inline-block;width:18px;height:4px;border-radius:2px}
.mono{font-family:'Seuntai Mono',ui-monospace,monospace;font-size:12.5px}
.mut{color:var(--mut)}.small{font-size:12.5px}
.filters{display:flex;gap:10px;align-items:center;margin:0 0 10px;flex-wrap:wrap}
.filters input[type=search],.gsearch{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:7px 10px;min-width:240px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chips button{font:600 12.5px 'Seuntai Text',sans-serif;border:1px solid var(--line);background:var(--card);color:var(--ink);
border-radius:999px;padding:5px 11px;cursor:pointer;display:inline-flex;gap:6px;align-items:center}
.chips button i{width:12px;height:4px;border-radius:2px;display:inline-block}
.chips button[aria-pressed=true]{background:var(--ink);color:var(--card);border-color:var(--ink)}
.chk input{accent-color:var(--coral)}
.progress{display:flex;align-items:center;gap:12px;margin:0 0 10px;flex-wrap:wrap}
.pbar{flex:1;min-width:180px;max-width:420px;height:10px;background:var(--line);border-radius:999px;overflow:hidden}
.pbar i{display:block;height:100%;width:0;background:var(--ok);transition:width .4s}
.tag{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600;border:1px solid}
.t-standar{color:#0072B2;border-color:#0072B2}.t-literatur{color:#009E73;border-color:#009E73}
.t-desain{color:#B36B00;border-color:#E69F00}
.kep td:first-child{min-width:230px}
.src{padding-left:20px;max-width:100ch}.src li{margin:0 0 6px}.src li:target{background:var(--hl)}
.chart{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px;max-width:900px}
.chart svg{width:100%;height:auto;display:block}.chart .hb{fill:#A898FF}.chart .cum{fill:none;stroke:#1A1033;stroke-width:2}
@media (prefers-color-scheme:dark){.chart .cum{stroke:#EEEAF8}}
.chart .gl{stroke:var(--line)}.chart .ax{font-size:11px;fill:var(--mut)}
.chart .mk{stroke-width:2}.chart .mk.tol{stroke:#FF4D6D}.chart .mk.knee{stroke:#0072B2;stroke-dasharray:5 4}
.chart .mk.road{stroke:#8C8C8C;stroke-dasharray:2 4}.chart .mt{font-size:11.5px;font-weight:600}
.chart .mt.tol{fill:#D6264A}.chart .mt.knee{fill:#0072B2}.chart .mt.road{fill:var(--mut)}
.chart .yk{fill:#009E73}.chart .yd{fill:#D55E00}
.checks{padding-left:20px;max-width:90ch}.checks li{margin:4px 0}.checks li.w{color:var(--warn);font-weight:600}
.faq details,#teknis details{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:0 0 8px}
.faq summary,#teknis summary{cursor:pointer;padding:12px 16px;font-weight:600}
.faq p{margin:0;padding:0 16px 14px;color:var(--mut);max-width:85ch}
#teknis details>*:not(summary){margin-left:16px;margin-right:16px}#teknis details{padding-bottom:12px}
.gloss{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;margin:12px 0 0}
.gloss div{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.gloss div:target{box-shadow:0 0 0 3px var(--amber)}
.gloss dt{font-weight:800;font-family:'Seuntai Display',sans-serif}.gloss dd{margin:4px 0 0;color:var(--mut);font-size:13.5px}
.story{position:fixed;z-index:2000;right:16px;top:132px;width:min(400px,calc(100vw - 32px));max-height:calc(100vh - 150px);
overflow:auto;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 20px;
box-shadow:0 18px 50px rgba(20,10,44,.28)}
.story h3{margin:0 0 10px;font-size:20px}
.story .x{position:absolute;right:10px;top:8px;border:0;background:none;font-size:26px;color:var(--mut);cursor:pointer}
.story .say{font-size:15px;margin:0 0 12px}
.story .meter{height:12px;border-radius:999px;background:var(--line);overflow:hidden;margin:4px 0 2px;position:relative}
.story .meter i{display:block;height:100%;background:#D55E00}
.story .meter b{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink)}
.story table{font-size:13px}.story td{padding:4px 0;border:0}.story td:first-child{color:var(--mut);padding-right:12px}
.story .why{font-size:12.5px;color:var(--mut);border-top:1px solid var(--line);padding-top:10px;margin-top:10px}
.story .btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.tour{position:fixed;inset:0;z-index:2800}
.spot{position:fixed;border-radius:14px;box-shadow:0 0 0 9999px rgba(10,5,25,.62);transition:all .35s;pointer-events:none}
.tcard{position:fixed;width:min(360px,calc(100vw - 32px));background:var(--card);color:var(--ink);border-radius:16px;
padding:16px 18px;box-shadow:0 18px 50px rgba(0,0,0,.4);transition:top .35s,left .35s}
.tcard h3{margin:0 0 6px}.tcard p{margin:0 0 12px}
footer{max-width:1320px;margin:0 auto;padding:18px 28px 36px;color:var(--mut);font-size:12.5px}
@media (max-width:1000px){.hero,.explainer{grid-template-columns:1fr}.rules{grid-template-columns:1fr 1fr}}
@media (max-width:640px){main,.top{padding-left:16px;padding-right:16px}.top .meta{margin-left:0}
.kpis{grid-template-columns:1fr 1fr}.mix{grid-template-columns:1fr;justify-items:center}.rules{grid-template-columns:1fr}
.mapsearch{left:12px;top:auto;bottom:30px;width:calc(100% - 24px)}.mapsearch ul{position:absolute;bottom:44px;left:0;right:0}.top{position:static}html{scroll-padding-top:12px}
.story{top:auto;bottom:12px;max-height:60vh}.mlegend{bottom:80px}.maptools{max-width:calc(100% - 24px)}}
@media print{.top{position:static}.tabs,.actions,.maptools,.mapsearch,.filters,.exbtns,.progress button,#cmpui,.story,.tip,
.tour{display:none!important}.tw{max-height:none;overflow:visible}body{background:#fff}.mapwrap{break-inside:avoid;height:460px}
details{display:block}details>*{display:block}section{break-inside:auto}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}html{scroll-behavior:auto}}
"""

JS = r"""
(function(){
"use strict";
var D=window.SEUNTAI;if(!D)return;var CF=D.cfg;
var ST={},NT={};D.st.forEach(function(s){ST[s[0]]={l:s[1],c:s[2],d:s[3]}});D.nt.forEach(function(n){NT[n[0]]={l:n[1],c:n[2]}});
var RM=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function $(id){return document.getElementById(id)}
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function fmt(x,d){if(x==null||x==="")return"-";return Number(x).toLocaleString("id-ID",{minimumFractionDigits:d||0,maximumFractionDigits:d||0})}
function km(m){return m>=1000?fmt(m/1000,2)+" km":fmt(m,m>=100?0:1)+" m"}
function stb(s){var t=ST[s]||{l:s,c:"#888"};return '<span class="st"><i style="background:'+t.c+'"></i>'+esc(t.l)+'</span>'}
function hk(k){return String(k||"").replace(/^(celah|jembatan) T ([\d.,]+ m) ke untai (\S+)/,function(_,a,d,u){return (a==="celah"?"Ujung berhenti ":"Disambung, ")+d+" dari sisi untai "+u}).replace(/^(celah|jembatan) segaris ([\d.,]+ m) ke untai (\S+)/,function(_,a,d,u){return (a==="celah"?"Ujung berhadapan dengan ujung untai ":"Ujung disambung lurus ke untai ")+u+", jarak "+d})}
function term(k,l){var g=D.gl[k];return '<span class="term" tabindex="0" data-t="'+k+'">'+esc(l||(g?g[0]:k))+'</span>'}
var byF={};D.G.forEach(function(g){byF[g.f]=g});
var store=null;try{store=window.localStorage;store.setItem("_s","1");store.removeItem("_s")}catch(e){store=null}
var SKEY="seuntai:"+CF.layer+":"+CF.run;

// ---------------------------------------------------------------- penjelasan istilah
var tip=$("tip");
function showTip(el){var g=D.gl[el.getAttribute("data-t")];if(!g)return;tip.innerHTML="<b>"+esc(g[0])+"</b>"+esc(g[1]);tip.hidden=false;
  var r=el.getBoundingClientRect(),tw=tip.offsetWidth,th=tip.offsetHeight;var x=Math.min(Math.max(8,r.left),window.innerWidth-tw-8);
  var y=r.bottom+8;if(y+th>window.innerHeight-8)y=r.top-th-8;tip.style.left=x+"px";tip.style.top=y+"px"}
function hideTip(){tip.hidden=true}
document.addEventListener("mouseover",function(e){var t=e.target.closest&&e.target.closest(".term");if(t)showTip(t)});
document.addEventListener("mouseout",function(e){var t=e.target.closest&&e.target.closest(".term");if(t)hideTip()});
document.addEventListener("focusin",function(e){if(e.target.classList&&e.target.classList.contains("term"))showTip(e.target)});
document.addEventListener("focusout",function(e){if(e.target.classList&&e.target.classList.contains("term"))hideTip()});
window.addEventListener("scroll",hideTip,{passive:true});

// ---------------------------------------------------------------- angka bergerak & navigasi
function countUp(){Array.prototype.forEach.call(document.querySelectorAll("[data-count]"),function(el){
  var to=+el.getAttribute("data-count");if(RM||to<10)return;var t0=null;
  function step(t){if(!t0)t0=t;var p=Math.min(1,(t-t0)/900);el.textContent=fmt(Math.round(to*(1-Math.pow(1-p,3))));if(p<1)requestAnimationFrame(step)}
  requestAnimationFrame(step)})}
countUp();
var tabs=Array.prototype.slice.call(document.querySelectorAll(".tabs a"));
if("IntersectionObserver" in window){var io=new IntersectionObserver(function(es){es.forEach(function(en){if(en.isIntersecting){
  tabs.forEach(function(a){a.classList.toggle("on",a.getAttribute("href")==="#"+en.target.id)})}})},{rootMargin:"-30% 0px -60% 0px"});
  tabs.forEach(function(a){var s=document.querySelector(a.getAttribute("href"));if(s)io.observe(s)})}

// ---------------------------------------------------------------- peta
var map=null,groups={},byId={S:{},G:{}},view="dec",hlLayers=[];
var HELP={dec:"Warna garis menunjukkan keputusan: hijau dipakai utuh, oranye dipangkas, merah duplikat dibuang."+(CF.qc?"":" Garis tebal koral = hasil."),
  before:"Data asli sebelum diproses: semua garis bertumpuk ditampilkan dengan warna sama. Perhatikan jalur yang tampak tebal karena ditumpuk berkali-kali.",
  after:"Hasil: satu garis per jalur. Inilah jaringan bersih yang disimpan sebagai kabel tunggal.",
  cmp:"Geser pembatas kuning: kiri = sebelum (garis bertumpuk), kanan = sesudah (hasil bersih)."};
if(window.L){
  map=L.map("map",{zoomControl:true,preferCanvas:true,attributionControl:true});window._map=map;
  ["pBefore","pAfter"].forEach(function(n,i){var p=map.createPane(n);p.style.zIndex=410+i*5;p.classList.add("pclip")});
  var rB=L.canvas({pane:"pBefore",padding:.5}),rA=L.canvas({pane:"pAfter",padding:.5});
  var gDec=L.featureGroup(),gStr=L.featureGroup(),gBef=L.featureGroup(),gAft=L.featureGroup(),gNC=L.featureGroup(),gNJ=L.featureGroup(),gNB=L.featureGroup();
  groups={NC:gNC,NJ:gNJ,NB:gNB};var nm=[],all=[],WL=[];
  D.G.forEach(function(g){
    var t=ST[g.s]||{c:"#888",d:""};var lines=g.x.filter(function(p){return p.length>1});if(!lines.length)return;
    var pl=L.polyline(lines,{color:t.c,weight:g.s==="DIPAKAI"?2.5:2,opacity:.9,dashArray:t.d||null});
    pl.on("click",function(){openStory(g.f,false)});pl.addTo(gDec);byId.G[g.f]=pl;all.push(pl);
    L.polyline(lines,{renderer:rB,color:"#C9C1E6",weight:2.2,opacity:.55,interactive:true}).on("click",function(){openStory(g.f,false)}).addTo(gBef);
  });
  function strandLayers(s,r){var fr=s.k==="FRAGMEN";var o=r?{renderer:r}:{};
    function P(st){var x={};for(var k in o)x[k]=o[k];for(var k2 in st)x[k2]=st[k2];var l=L.polyline(s.x,x);l._w0=st.weight;WL.push(l);return l}
    return L.featureGroup([P({color:"#140A2C",weight:fr?6:10,opacity:.85,lineCap:"round",lineJoin:"round"}),
      P({color:fr?"#CC79A7":"#FF4D6D",weight:fr?3.5:6,opacity:1,lineCap:"round",lineJoin:"round"}),
      P({color:"#FFB703",weight:2,opacity:1,lineCap:"round",lineJoin:"round"})])}
  D.S.forEach(function(s){var a=strandLayers(s,null);a.bindPopup(function(){return popS(s)});a.addTo(gStr);byId.S[s.i]=a;
    var b=strandLayers(s,rA);b.bindPopup(function(){return popS(s)});b.addTo(gAft)});
  D.N.forEach(function(n){
    var t=NT[n.j]||{c:"#888"};var r=n.j==="UJUNG"?3.5:(n.j==="CABANG"?5:7);
    var m=L.circleMarker([n.a,n.o],{radius:r,color:"#fff",weight:1.5,fillColor:t.c,fillOpacity:1,pane:"markerPane"});m._r0=r;nm.push(m);
    m.bindPopup('<div class="pop"><h4>'+esc(t.l)+'</h4><table><tr><td>Untai</td><td>'+esc(n.i||"-")+'</td></tr>'+
      (n.d!=null?'<tr><td>Jarak</td><td>'+fmt(n.d,2)+' m</td></tr>':'')+'<tr><td>Keterangan</td><td>'+esc(hk(n.k))+
      '</td></tr><tr><td>Koordinat</td><td class="mono">'+n.a.toFixed(6)+', '+n.o.toFixed(6)+'</td></tr></table></div>');
    m.addTo(n.j==="CELAH"?gNC:(n.j==="JEMBATAN"?gNJ:gNB));n._m=m;
  });
  function rs(){var z=map.getZoom(),f=Math.max(.35,Math.min(1,(z-11)/5)),w=z<10?.55:(z<13?.75:(z<15?.9:1));nm.forEach(function(m){m.setRadius(m._r0*f)});
    WL.forEach(function(l){l.setStyle({weight:Math.max(1.2,l._w0*w)})})}
  map.on("zoomend",rs);
  var b=L.featureGroup(all).getBounds();if(b.isValid())map.fitBounds(b,{padding:[24,24]});else map.setView([-2,118],5);
  rs();L.control.scale({imperial:false}).addTo(map);
  var osm=null;
  $("osm").addEventListener("change",function(e){
    if(e.target.checked){osm=osm||L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,
      attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'});osm.addTo(map);osm.bringToBack();}
    else if(osm){map.removeLayer(osm)}});
  Array.prototype.forEach.call(document.querySelectorAll(".maptools input[data-l]"),function(cb){
    cb.addEventListener("change",function(){var g=groups[cb.getAttribute("data-l")];if(cb.checked)g.addTo(map);else map.removeLayer(g)})});
  // tampilan
  var pB=map.getPane("pBefore"),pA=map.getPane("pAfter"),wrap=$("mapwrap"),rng=$("cmprange"),dv=$("divider");
  L.DomEvent.disableClickPropagation($("cmpui"));L.DomEvent.disableScrollPropagation($("cmpui"));
  L.DomEvent.disableClickPropagation(document.querySelector(".mapsearch"));L.DomEvent.disableScrollPropagation(document.querySelector(".mapsearch"));
  function clip(){if(view!=="cmp"){pB.style.clip="";pA.style.clip="";return}
    var sz=map.getSize(),x=sz.x*rng.value/100;dv.style.left=x+"px";
    var nw=map.containerPointToLayerPoint([0,0]),se=map.containerPointToLayerPoint(sz),cx=map.containerPointToLayerPoint([x,0]).x;
    pB.style.clip="rect("+[nw.y,cx,se.y,nw.x].join("px,")+"px)";pA.style.clip="rect("+[nw.y,se.x,se.y,cx].join("px,")+"px)"}
  map.on("move zoom resize",clip);rng.addEventListener("input",clip);
  function legendFor(v){var h="";
    if(v==="dec"){D.st.forEach(function(s){if(D.G.some(function(g){return g.s===s[0]}))h+='<div><i style="background:'+s[2]+'"></i>'+esc(s[1])+'</div>'});
      if(!CF.qc)h+='<div><i style="background:#FF4D6D"></i>Hasil (untai)</div>'}
    else if(v==="before")h='<div><i style="background:#C9C1E6"></i>Semua garis asli</div>';
    else if(v==="after")h='<div><i style="background:#FF4D6D"></i>Hasil: 1 garis per jalur</div><div><i style="background:#CC79A7"></i>Fragmen pendek</div>';
    else h='<div><i style="background:#C9C1E6"></i>Kiri: sebelum</div><div><i style="background:#FF4D6D"></i>Kanan: sesudah</div>';
    $("mlegend").innerHTML=h}
  window._setView=function(v){view=v;if(v==='after'||v==='cmp')clearHl();[gDec,gStr,gBef,gAft].forEach(function(g){map.removeLayer(g)});
    if(v==="dec"){gDec.addTo(map);gStr.addTo(map)}else if(v==="before")gBef.addTo(map);else if(v==="after")gAft.addTo(map);
    else{gBef.addTo(map);gAft.addTo(map)}
    $("cmpui").hidden=v!=="cmp";clip();legendFor(v);$("viewhelp").textContent=HELP[v];
    Array.prototype.forEach.call(document.querySelectorAll(".seg button"),function(b){b.setAttribute("aria-pressed",b.getAttribute("data-v")===v?"true":"false")})};
  Array.prototype.forEach.call(document.querySelectorAll(".seg button"),function(b){b.addEventListener("click",function(){window._setView(b.getAttribute("data-v"))})});
  window._setView("dec");
  $("fsbtn").addEventListener("click",function(){try{if(document.fullscreenElement)document.exitFullscreen();else wrap.requestFullscreen()}catch(e){}});
  document.addEventListener("fullscreenchange",function(){setTimeout(function(){map.invalidateSize();clip()},120)});
}else{$("viewhelp").textContent="Peta tidak dapat dimuat di peramban ini."}
function popS(s){return '<div class="pop"><h4>'+esc(s.i)+(s.k==="FRAGMEN"?" (fragmen)":"")+'</h4><table><tr><td>Panjang</td><td>'+km(s.L)+'</td></tr>'+
  (s.g?'<tr><td>Grup</td><td>'+esc(s.g)+'</td></tr>':'')+'<tr><td>Garis sumber</td><td>'+s.o+'</td></tr>'+
  '<tr><td>Ruas / cabang / ujung</td><td>'+s.r+' / '+s.b+' / '+s.e+'</td></tr><tr><td>Utuh</td><td>'+(s.u?"Ya":"Tidak, bercabang")+'</td></tr>'+
  '<tr><td>Tanggal tertua</td><td>'+esc(s.t0||"-")+'</td></tr><tr><td>FID sumber</td><td class="mono">'+esc(s.fo.slice(0,30).join(", "))+(s.fo.length>30?" …":"")+'</td></tr></table></div>'}
function toMap(){var m=$("peta");if(m)m.scrollIntoView({behavior:RM?"auto":"smooth",block:"start"})}
function clearHl(){hlLayers.forEach(function(x){if(map)map.removeLayer(x)});hlLayers=[]}
function highlight(fids,nofit){clearHl();if(!map)return null;var bb=null;
  fids.forEach(function(f,i){var g=byF[f];if(!g)return;var lines=g.x.filter(function(p){return p.length>1});if(!lines.length)return;
    var h=L.polyline(lines,{color:i===0?"#FFFFFF":"#2EE6A6",weight:i===0?9:7,opacity:.95,interactive:false,dashArray:i===0?null:"10 8"});
    var h2=L.polyline(lines,{color:i===0?"#FF4D6D":"#007A5A",weight:i===0?4:3,opacity:1,interactive:false});
    h.addTo(map);h2.addTo(map);hlLayers.push(h,h2);var b=h.getBounds();bb=bb?bb.extend(b):L.latLngBounds(b.getSouthWest(),b.getNorthEast())});
  if(!nofit&&bb&&bb.isValid())map.fitBounds(bb,{padding:[60,60],maxZoom:19});return bb}
function zoomStrand(id){var l=byId.S[id];if(!map||!l)return;if(view!=="dec")window._setView("dec");var b=l.getBounds();
  if(b.isValid())map.fitBounds(b,{padding:[40,40],maxZoom:19});l.openPopup(b.getCenter());toMap()}

// ---------------------------------------------------------------- cerita garis
function story(g){var o=g.d?byF[g.d]:null,lead=CF.nodate?"lebih panjang":"lebih tua",
  who=o?('FID <b>'+esc(o.f)+'</b>'+(o.nm?' ('+esc(o.nm)+')':'')+(o.t?', dibuat '+esc(o.t):'')+', urutan '+o.r):"",s="";
  if(g.s==="DUPLIKAT")s='<b>'+fmt(g.c,0)+'%</b> panjang garis ini berada di dalam '+term("koridor","koridor")+' garis '+who+' yang '+lead+
    '. Karena melewati ambang '+fmt(CF.cover,0)+'%, garis ini dianggap salinan dan <b>tidak ikut di hasil</b>.';
  else if(g.s==="DIPANGKAS")s='Sebagian garis ini (<b>'+fmt(g.c,0)+'%</b>) berjalan sejajar dengan garis '+(who||"lain")+' yang '+lead+
    '. Bagian sejajar itu dibuang; sisanya <b>'+km(g.k)+'</b> dari '+km(g.L)+' tetap dipakai dan disambungkan.';
  else if(g.s==="DIPAKAI")s='Garis ini <b>dipakai utuh</b>'+(g.c>0&&o?': hanya '+fmt(g.c,0)+'% yang bersinggungan dengan garis '+who+', jauh di bawah ambang '+fmt(CF.cover,0)+'%.':
    ': tidak ada garis lain yang lebih diutamakan di jalurnya.');
  else if(g.s==="SERPIHAN")s='Setelah bagian sejajarnya dipangkas, sisa garis ini terlalu pendek sehingga '+term("serpihan","dibuang sebagai serpihan")+'.';
  else s='Garis ini tidak punya geometri sehingga tidak bisa diproses.';
  var m=(g.s==="DUPLIKAT"||g.s==="DIPANGKAS"||(g.s==="DIPAKAI"&&g.c>0))?'<p class="small mut">Bagian yang menumpuk</p><div class="meter"><i style="width:'+
    Math.min(100,g.c)+'%"></i><b style="left:'+CF.cover+'%" title="ambang duplikat"></b></div><p class="small mut">Garis hitam = ambang duplikat '+fmt(CF.cover,0)+'%</p>':"";
  return '<p class="say">'+s+'</p>'+m+'<table><tr><td>Status</td><td>'+stb(g.s)+'</td></tr>'+
    (g.nm?'<tr><td>Nama kabel</td><td>'+esc(g.nm)+'</td></tr>':'')+(g.p?'<tr><td>Produk</td><td>'+esc(g.p)+'</td></tr>':'')+
    '<tr><td>Tanggal dibuat</td><td>'+esc(g.t||"tidak ada / tidak terbaca")+'</td></tr><tr><td>'+term("prioritas","Urutan prioritas")+'</td><td>'+g.r+' dari '+fmt(D.G.length)+'</td></tr>'+
    '<tr><td>Panjang</td><td>'+km(g.L)+' (dipakai '+km(g.k)+')</td></tr>'+(g.u?'<tr><td>Untai</td><td>'+esc(g.u)+'</td></tr>':'')+'</table>'+
    '<div class="btns"><button class="btn primary" type="button" data-hl="'+esc(g.f)+'">Tampilkan di peta</button>'+
    (o?'<button class="btn" type="button" data-hl2="'+esc(g.f)+'">Bandingkan dengan pemenangnya</button><button class="btn" type="button" data-open="'+esc(o.f)+'">Cerita FID '+esc(o.f)+'</button>':'')+'</div>'+
    (g.n?'<p class="why">Catatan teknis: '+esc(g.n)+'</p>':'')}
function openStory(f,go){var g=byF[f];if(!g)return;$("sttitle").textContent="FID "+g.f+(g.nm?" · "+g.nm:"");$("stbody").innerHTML=story(g);
  $("story").hidden=false;Array.prototype.forEach.call(document.querySelectorAll("#t-garis tr.sel"),function(r){r.classList.remove("sel")});
  if(go){if(view!=="dec"&&view!=="before")window._setView("dec");highlight([g.f]);toMap()}else highlight([g.f],true)}
$("stclose").addEventListener("click",function(){$("story").hidden=true;clearHl()});
document.addEventListener("keydown",function(e){if(e.key==="Escape"){$("story").hidden=true;clearHl();endTour()}});
$("story").addEventListener("click",function(e){var b=e.target.closest("button");if(!b)return;
  if(b.hasAttribute("data-hl")){highlight([b.getAttribute("data-hl")]);toMap()}
  else if(b.hasAttribute("data-hl2")){var g=byF[b.getAttribute("data-hl2")];if(view==="after"||view==="cmp")window._setView("dec");highlight([g.f,g.d]);toMap()}
  else if(b.hasAttribute("data-open"))openStory(b.getAttribute("data-open"),true)});

// ---------------------------------------------------------------- pencarian di peta
var ms=$("msearch"),mr=$("mresults");
function doSearch(){var q=(ms.value||"").trim().toLowerCase();if(!q){mr.innerHTML="";return}
  var hit=D.G.filter(function(g){return g.f.toLowerCase()===q||(g.nm&&g.nm.toLowerCase().indexOf(q)>=0)||g.f.toLowerCase().indexOf(q)===0}).slice(0,8);
  mr.innerHTML=hit.map(function(g,i){return '<li role="option" data-f="'+esc(g.f)+'"'+(i===0?' aria-selected="true"':'')+'>FID '+esc(g.f)+(g.nm?' · '+esc(g.nm):'')+' — '+esc((ST[g.s]||{}).l||g.s)+'</li>'}).join("")||'<li>Tidak ditemukan</li>'}
ms.addEventListener("input",doSearch);
ms.addEventListener("keydown",function(e){if(e.key==="Enter"){var li=mr.querySelector("li[data-f]");if(li){openStory(li.getAttribute("data-f"),true);mr.innerHTML=""}}});
mr.addEventListener("click",function(e){var li=e.target.closest("li[data-f]");if(li){openStory(li.getAttribute("data-f"),true);mr.innerHTML=""}});

// ---------------------------------------------------------------- animasi cara kerja
var EX=[["Data awal","Tiga garis digambar di jalan yang sama: A, B, dan C. Di peta terlihat seperti satu garis tebal, padahal bertumpuk."],
  [CF.nodate?"Urutkan dari yang terpanjang":"Urutkan dari yang tertua",CF.nodate?"Data tanpa tanggal: garis terpanjang diperiksa lebih dulu.":"Setiap garis diberi nomor urut menurut tanggal pembuatan. A (2019) paling tua, jadi diperiksa lebih dulu dan diutamakan."],
  ["Garis pertama membuat koridor","A dipakai. Di sekelilingnya terbentuk koridor selebar "+fmt(CF.tol*2,0)+" m (toleransi "+fmt(CF.tol,1)+" m ke kiri dan kanan)."],
  ["Duplikat dibuang","Hampir seluruh B berada di dalam koridor A (di atas "+fmt(CF.cover,0)+"%). B dianggap salinan dan dibuang."],
  ["Bagian sejajar dipangkas","Awal garis C berjalan sejajar dengan A, sehingga bagian itu dipangkas. Ujung C yang berbelok ke jalan lain adalah jalur unik dan tetap dipakai."],
  ["Hasil: satu garis per jalur",CF.qc?"Begitulah hasilnya bila data dikonsolidasikan.":"Tersisa A dan bagian unik C. Pada data Anda: "+fmt(CF.n_used)+" garis dipakai utuh, "+fmt(CF.n_trim)+" dipangkas, "+fmt(CF.n_dup)+" dibuang, menjadi "+fmt(CF.n_kabel)+" kabel tunggal."]];
if(CF.nodate){$("bA").textContent="A · terpanjang";$("bB").textContent="B · #2";$("bC").textContent="C · #3"}
var exi=0,exT=null,svg=$("exsvg"),sl=$("exsteps");
sl.innerHTML=EX.map(function(s,i){return '<li data-i="'+i+'" tabindex="0">'+esc(s[0])+'</li>'}).join("");
function exGo(i){exi=(i+EX.length)%EX.length;svg.setAttribute("class","ex s"+(exi+1));$("excap").innerHTML="<b>"+esc(EX[exi][0])+".</b> "+esc(EX[exi][1]);
  Array.prototype.forEach.call(sl.children,function(li,k){li.classList.toggle("on",k===exi)})}
function exStop(){if(exT){clearInterval(exT);exT=null;$("explay").textContent="Putar"}}
sl.addEventListener("click",function(e){var li=e.target.closest("li");if(li){exStop();exGo(+li.getAttribute("data-i"))}});
sl.addEventListener("keydown",function(e){if(e.key==="Enter"){var li=e.target.closest("li");if(li){exStop();exGo(+li.getAttribute("data-i"))}}});
$("exprev").addEventListener("click",function(){exStop();exGo(exi-1)});$("exnext").addEventListener("click",function(){exStop();exGo(exi+1)});
$("explay").addEventListener("click",function(){if(exT){exStop();return}$("explay").textContent="Jeda";if(exi===EX.length-1)exGo(0);
  exT=setInterval(function(){if(exi===EX.length-1){exStop();return}exGo(exi+1)},2600)});
exGo(0);

// ---------------------------------------------------------------- umur jaringan
(function(){var el=$("yearchart");if(!el)return;var Y={};D.G.forEach(function(g){if(!g.t)return;var y=g.t.slice(0,4);Y[y]=Y[y]||[0,0];
  if(g.s==="DIPAKAI"||g.s==="DIPANGKAS")Y[y][0]++;else if(g.s==="DUPLIKAT"||g.s==="SERPIHAN")Y[y][1]++});
  var ys=Object.keys(Y).sort();if(!ys.length){el.style.display="none";return}
  var W=760,H=240,L=44,B=34,T=16,R=10,mx0=Math.max.apply(null,ys.map(function(y){return Y[y][0]+Y[y][1]}))||1,st=Math.pow(10,Math.floor(Math.log10(mx0/4))),mx=4*([1,1.5,2,2.5,3,4,5,6,8,10].map(function(m){return m*st}).filter(function(s){return s*4>=mx0})[0]||10*st),bw=(W-L-R)/ys.length,p=[];
  for(var i=0;i<=4;i++){var v=mx*i/4,yy=T+(H-T-B)*(1-i/4);p.push('<line x1="'+L+'" x2="'+(W-R)+'" y1="'+yy+'" y2="'+yy+'" class="gl"/><text x="'+(L-6)+'" y="'+(yy+4)+'" class="ax" text-anchor="end">'+fmt(v)+'</text>')}
  ys.forEach(function(y,i){var k=Y[y][0],d=Y[y][1],x=L+i*bw+bw*.15,w=bw*.7,hk=(H-T-B)*k/mx,hd=(H-T-B)*d/mx,base=H-B;
    p.push('<rect class="yk" x="'+x+'" y="'+(base-hk)+'" width="'+w+'" height="'+hk+'"><title>'+y+': '+k+' dipertahankan</title></rect>');
    p.push('<rect class="yd" x="'+x+'" y="'+(base-hk-hd)+'" width="'+w+'" height="'+hd+'"><title>'+y+': '+d+' dibuang</title></rect>');
    p.push('<text x="'+(x+w/2)+'" y="'+(H-B+16)+'" class="ax" text-anchor="middle">'+y+'</text>')});
  p.push('<rect x="'+(W-210)+'" y="4" width="12" height="12" class="yk"/><text x="'+(W-194)+'" y="14" class="ax">dipertahankan</text><rect x="'+(W-110)+'" y="4" width="12" height="12" class="yd"/><text x="'+(W-94)+'" y="14" class="ax">dibuang</text>');
  el.innerHTML='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Jumlah garis per tahun pembuatan">'+p.join("")+'</svg>'})();

// ---------------------------------------------------------------- tabel untai
var tu=document.querySelector("#t-untai tbody");
function drawU(){if(!tu)return;var hf=$("hidefrag").checked;var rows=D.S.filter(function(s){return !hf||s.k!=="FRAGMEN"});
  tu.innerHTML=rows.slice(0,2000).map(function(s){return '<tr data-z="S:'+esc(s.i)+'" tabindex="0"><td><b>'+esc(s.i)+'</b></td><td>'+(s.k==="FRAGMEN"?"Fragmen":"Utama")+'</td><td>'+esc(s.g||"-")+
  '</td><td class="r">'+km(s.L)+'</td><td class="r">'+s.o+'</td><td class="r">'+s.r+'</td><td class="r">'+s.b+'</td><td class="r">'+s.e+
  '</td><td>'+(s.u?"Ya":"Tidak")+'</td><td>'+esc(s.t0||"-")+'</td><td class="r">'+(s.j?fmt(s.j,1)+" m":"-")+'</td></tr>'}).join("")||'<tr><td colspan="11">Tidak ada untai.</td></tr>';
  $("cntu").textContent=fmt(rows.length)+" dari "+fmt(D.S.length)+" untai"+(rows.length>2000?" (2.000 pertama ditampilkan)":"")}
if(tu){$("hidefrag").addEventListener("change",drawU);drawU()}

// ---------------------------------------------------------------- tabel keputusan
var tg=document.querySelector("#t-garis tbody"),q=$("q"),fsel="",LIM=1500,chips=$("chips");
var chipH='<button type="button" data-s="" aria-pressed="true">Semua ('+fmt(D.G.length)+')</button>';
D.st.forEach(function(s){var n=D.G.filter(function(g){return g.s===s[0]}).length;if(n)chipH+='<button type="button" data-s="'+s[0]+'" aria-pressed="false"><i style="background:'+s[2]+'"></i>'+esc(s[1])+' ('+fmt(n)+')</button>'});
chips.innerHTML=chipH;
chips.addEventListener("click",function(e){var b=e.target.closest("button");if(!b)return;fsel=b.getAttribute("data-s");
  Array.prototype.forEach.call(chips.children,function(c){c.setAttribute("aria-pressed",c===b?"true":"false")});drawG()});
function rowsG(){var qq=(q.value||"").toLowerCase();return D.G.filter(function(g){return(!fsel||g.s===fsel)&&(!qq||(g.f+" "+g.nm+" "+g.u+" "+g.n+" "+g.d+" "+g.g+" "+g.p).toLowerCase().indexOf(qq)>=0)})}
function drawG(){var rows=rowsG();
  tg.innerHTML=rows.slice(0,LIM).map(function(g){return '<tr data-z="G:'+esc(g.f)+'" tabindex="0"><td class="r">'+g.r+'</td><td class="mono">'+esc(g.f)+
    '</td><td>'+esc(g.nm||"-")+'</td><td>'+stb(g.s)+'</td><td class="nw">'+esc(g.t||"-")+'</td><td class="r nw">'+km(g.L)+'</td><td class="r nw">'+km(g.k)+
    '</td><td class="r">'+fmt(g.c,0)+'%</td><td class="mono">'+(g.d&&g.s!=="DIPAKAI"?esc(g.d):"-")+'</td><td>'+esc(g.u||"-")+'</td></tr>'}).join("");
  $("cnt").textContent=fmt(rows.length)+" garis";
  $("more").textContent=rows.length>LIM?("Ditampilkan "+fmt(LIM)+" baris pertama; gunakan pencarian, atau buka layer keputusan di QGIS untuk semua garis."):""}
q.addEventListener("input",drawG);drawG();
function csv(rows,cols,name){var s="﻿"+cols.map(function(c){return c[0]}).join(";")+"\n"+rows.map(function(r){return cols.map(function(c){var v=c[1](r);v=v==null?"":String(v);
  return /[;"\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}).join(";")}).join("\n");
  var a=document.createElement("a");a.href=URL.createObjectURL(new Blob([s],{type:"text/csv;charset=utf-8"}));a.download=name;document.body.appendChild(a);a.click();
  setTimeout(function(){URL.revokeObjectURL(a.href);a.remove()},500)}
var base=(CF.layer||"seuntai").replace(/[^A-Za-z0-9_-]+/g,"_");
$("csvg").addEventListener("click",function(){csv(rowsG(),[["urutan",function(g){return g.r}],["fid",function(g){return g.f}],["nama",function(g){return g.nm}],
  ["produk",function(g){return g.p}],["status",function(g){return g.s}],["tanggal",function(g){return g.t}],["panjang_m",function(g){return String(g.L).replace(".",",")}],
  ["dipakai_m",function(g){return String(g.k).replace(".",",")}],["menumpuk_pct",function(g){return g.c}],["kalah_dari_fid",function(g){return g.s!=="DIPAKAI"?g.d:""}],
  ["untai",function(g){return g.u}],["alasan",function(g){return g.n}]],"Seuntai_keputusan_"+base+".csv")});

// ---------------------------------------------------------------- celah: daftar periksa
var tc=document.querySelector("#t-cat tbody"),done={};
try{if(store)done=JSON.parse(store.getItem(SKEY)||"{}")||{}}catch(e){done={}}
var cn=D.N.map(function(n,i){n._i=i;return n}).filter(function(n){return n.j==="CELAH"}).concat(D.N.filter(function(n){return n.j==="JEMBATAN"}));
function drawC(){tc.innerHTML=cn.slice(0,1500).map(function(n){var d=!!done[n._i];return '<tr data-z="N:'+n._i+'" tabindex="0" class="'+(d?"done":"")+'"><td>'+
  (n.j==="CELAH"?'<input type="checkbox" data-c="'+n._i+'" aria-label="Sudah dicek"'+(d?" checked":"")+'>':'<span class="mut">otomatis</span>')+'</td><td>'+esc((NT[n.j]||{}).l||n.j)+'</td><td>'+esc(n.i||"-")+
  '</td><td class="r">'+(n.d!=null?fmt(n.d,2)+" m":"-")+'</td><td>'+esc(hk(n.k))+'</td><td class="mono">'+n.a.toFixed(6)+', '+n.o.toFixed(6)+'</td></tr>'}).join("")||
  '<tr><td colspan="6">Tidak ada celah dalam radius pelaporan.</td></tr>';prog()}
function prog(){var tot=cn.filter(function(n){return n.j==="CELAH"}).length,ok=cn.filter(function(n){return n.j==="CELAH"&&done[n._i]}).length;
  $("pfill").style.width=(tot?100*ok/tot:100)+"%";$("ptext").textContent=tot?(fmt(ok)+" dari "+fmt(tot)+" celah sudah dicek"):"Tidak ada celah yang perlu dicek"}
tc.addEventListener("change",function(e){var c=e.target.getAttribute&&e.target.getAttribute("data-c");if(c==null)return;if(e.target.checked)done[c]=1;else delete done[c];
  try{if(store)store.setItem(SKEY,JSON.stringify(done))}catch(err){}e.target.closest("tr").classList.toggle("done",e.target.checked);prog()});
tc.addEventListener("click",function(e){if(e.target.matches&&e.target.matches("input"))e.stopPropagation()},true);
drawC();
$("csvc").addEventListener("click",function(){csv(cn,[["jenis",function(n){return n.j}],["untai",function(n){return n.i}],["jarak_m",function(n){return n.d==null?"":String(n.d).replace(".",",")}],
  ["keterangan",function(n){return n.k}],["lintang",function(n){return n.a}],["bujur",function(n){return n.o}],["sudah_dicek",function(n){return n.j==="CELAH"?(done[n._i]?"ya":"belum"):"otomatis"}]],"Seuntai_celah_"+base+".csv")});

// ---------------------------------------------------------------- klik baris
function act(tr){var z=tr.getAttribute("data-z");if(!z)return;var k=z.slice(0,1),id=z.slice(2);
  if(k==="N"){var n=D.N[+id];if(n&&n._m&&map){var gk=n.j==="CELAH"?"NC":(n.j==="JEMBATAN"?"NJ":"NB");
    if(!map.hasLayer(groups[gk])){groups[gk].addTo(map);var cb=document.querySelector('.maptools input[data-l="'+gk+'"]');if(cb)cb.checked=true}
    map.setView([n.a,n.o],19);n._m.openPopup();toMap()}}
  else if(k==="G"){openStory(id,true);tr.classList.add("sel")}else zoomStrand(id)}
document.addEventListener("click",function(e){if(e.target.closest&&e.target.closest("input,button,a,.term"))return;var tr=e.target.closest&&e.target.closest("tr[data-z]");if(tr)act(tr)});
document.addEventListener("keydown",function(e){if(e.key==="Enter"&&e.target.matches&&e.target.matches("tr[data-z]"))act(e.target)});

// ---------------------------------------------------------------- kamus
$("gq").addEventListener("input",function(){var v=this.value.toLowerCase();Array.prototype.forEach.call($("gloss").children,function(d){d.style.display=d.textContent.toLowerCase().indexOf(v)>=0?"":"none"})});
document.addEventListener("click",function(e){var t=e.target.closest&&e.target.closest(".term");if(t&&window.matchMedia("(hover: none)").matches){showTip(t);setTimeout(hideTip,3500)}});

// ---------------------------------------------------------------- tur singkat
var TOUR=[["#ringkasan","Hasil dalam satu kalimat","Bagian atas merangkum hasil dan daftar 'Siap dipakai?'. Tanda seru oranye berarti ada yang perlu Anda cek."],
  ["#peta","Peta interaktif","Pilih tampilan Keputusan, Sebelum, Sesudah, atau Bandingkan. Klik garis untuk membaca ceritanya, atau cari FID/nama kabel di kotak pencarian."],
  ["#cara","Cara kerja","Animasi singkat ini menunjukkan bagaimana tumpukan dibereskan: urutkan, bandingkan dengan koridor, putuskan, sambungkan."],
  ["#garis","Keputusan per garis","Setiap garis beserta alasannya. Saring dengan tombol status, cari, dan unduh sebagai CSV untuk Excel."],
  ["#celah","Daftar periksa celah","Centang setiap celah yang sudah Anda periksa. Kemajuannya tersimpan di peramban ini."],
  ["#istilah","Kamus istilah","Istilah bergaris titik-titik di seluruh laporan punya penjelasan singkat. Selamat memeriksa!"]];
var ti=0,tour=$("tour");
function tourShow(){var s=document.querySelector(TOUR[ti][0]);if(!s){tourNext();return}s.scrollIntoView({behavior:"instant",block:"start"});
  setTimeout(function(){var r=s.getBoundingClientRect(),sp=$("tspot"),top=Math.max(r.top,120),h=Math.min(r.bottom,window.innerHeight-10)-top;
    sp.style.left=(r.left-8)+"px";sp.style.top=(top-8)+"px";sp.style.width=(r.width+16)+"px";sp.style.height=(Math.max(h,80)+16)+"px";
    var c=$("tcard");$("tstep").textContent="Langkah "+(ti+1)+" dari "+TOUR.length;$("ttitle").textContent=TOUR[ti][1];$("ttext").textContent=TOUR[ti][2];
    $("tnext").textContent=ti===TOUR.length-1?"Selesai":"Lanjut";
    var cy=Math.min(window.innerHeight-c.offsetHeight-16,top+40),cx=Math.min(window.innerWidth-c.offsetWidth-16,Math.max(16,r.right-c.offsetWidth-24));
    c.style.top=cy+"px";c.style.left=cx+"px";$("tnext").focus()},60)}
function tourNext(){ti++;if(ti>=TOUR.length){endTour();return}tourShow()}
function endTour(){tour.hidden=true}
$("tourbtn").addEventListener("click",function(){ti=0;tour.hidden=false;tourShow()});
$("tnext").addEventListener("click",tourNext);$("tskip").addEventListener("click",endTour);
window.addEventListener("resize",function(){if(!tour.hidden)tourShow()});
})();
"""
