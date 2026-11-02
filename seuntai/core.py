# -*- coding: utf-8 -*-
"""
Seuntai - inti algoritma konsolidasi strand (Python murni, tanpa QGIS, bisa diuji terpisah).

Masalah: beberapa garis berjalan berdampingan / bertumpuk di satu koridor (multilines). Garis-garis itu jarang
identik persis: hasil digitasi ulang, ekspor ulang, atau survei berbeda selalu bergeser beberapa sentimeter
sampai beberapa meter. Karena itu kesamaan diukur dengan JARAK (toleransi koridor), bukan kesamaan WKT.

Alur:
  1. Garis diurutkan menurut prioritas (default: tanggal pembuatan tertua dulu, lalu yang terpanjang, lalu FID).
  2. Garis diterima satu per satu. Setiap garis dicek terhadap garis yang SUDAH diterima: bagian yang berada di
     dalam toleransi koridor dianggap tumpang-tindih (paralel). Bila cakupan >= ambang -> DUPLIKAT (dibuang,
     dicatat duplikat dari garis mana). Bila sebagian -> bagian yang tumpang-tindih dipangkas, sisanya disambung
     ke garis pemilik koridor (mode 'pangkas'), atau garis dipakai utuh (mode 'utuh').
  3. Semua potongan yang dipakai di-noding (sambung ujung yang hampir bertemu, pecah di pertigaan dan
     persilangan), lalu digabung (line merge) menjadi untai: satu fitur per komponen tersambung.
  4. Celah antar-untai diukur; celah <= toleransi sambung bisa dijembatani otomatis.

Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-2.0-or-later (see LICENSE).
"""
import datetime as _dt
import math
import re
from array import array

# ------------------------------------------------------------------------------------------------ tanggal
_BULAN = {
    "jan": 1, "januari": 1, "january": 1, "feb": 2, "februari": 2, "february": 2, "peb": 2, "pebruari": 2,
    "mar": 3, "maret": 3, "march": 3, "apr": 4, "april": 4, "mei": 5, "may": 5, "jun": 6, "juni": 6, "june": 6,
    "jul": 7, "juli": 7, "july": 7, "agu": 8, "agt": 8, "agus": 8, "agustus": 8, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "okt": 10, "oct": 10, "oktober": 10, "october": 10,
    "nov": 11, "nop": 11, "november": 11, "nopember": 11, "des": 12, "dec": 12, "desember": 12, "december": 12,
}
_RX_ISO = re.compile(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T](\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?)?")
_RX_DMY = re.compile(r"^\s*(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})(?:[ T](\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?)?")
_RX_8 = re.compile(r"^\s*(\d{4})(\d{2})(\d{2})(?:[ T]?(\d{2})(\d{2})(\d{2})?)?\s*$")
_RX_NAMA = re.compile(r"^\s*(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{4})")
_RX_NAMA2 = re.compile(r"^\s*([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})")


def _mk(y, mo, d, h=0, mi=0, s=0):
    try:
        y, mo, d = int(y), int(mo), int(d)
        if y < 100:
            y += 2000 if y < 70 else 1900
        return _dt.datetime(y, mo, d, int(h or 0), int(mi or 0), int(s or 0))
    except (TypeError, ValueError):
        return None


DATE_MIN_YEAR = 1980     # tanggal sebelum ini = nilai pengganti/rusak (mis. 1899-12-30, 1900-01-01, epoch 1970)


def parse_date(v, dayfirst=True, today=None):
    """Seperti _parse_date_raw, ditambah uji kewajaran: tanggal sebelum 1980 (nilai pengganti seperti 1899-12-30,
    1900-01-01, 0000-00-00, epoch 1970, atau angka ID yang terbaca sebagai detik) dan tanggal lebih dari satu hari
    di masa depan dianggap TIDAK terbaca (None), sehingga tidak pernah menjadi 'tertua'."""
    d = _parse_date_raw(v, dayfirst)
    if d is None:
        return None
    lim = (today or _dt.datetime.now()) + _dt.timedelta(days=1)
    if d.year < DATE_MIN_YEAR or d > lim:
        return None
    return d


def _parse_date_raw(v, dayfirst=True):
    """Ubah nilai atribut tanggal menjadi datetime. Mengembalikan None bila kosong/tidak terbaca.

    Diterima: datetime/date Python, QDate/QDateTime/QVariant, string ISO (2019-05-03, 2019/05/03 10:20:00,
    2019-05-03T10:20), D/M/Y (03/05/2019; dayfirst=True mengikuti kebiasaan Indonesia, False = M/D/Y),
    20190503, nama bulan Indonesia/Inggris (3 Mei 2019, May 3, 2019), angka serial Excel, dan epoch (detik/ms).
    Tanggal yang tidak terbaca TIDAK dianggap tertua (kesalahan skrip panduan: datetime.min); pemanggil
    menaruhnya di urutan prioritas paling akhir.
    """
    if v is None:
        return None
    # QVariant NULL / QDate / QDateTime
    try:
        if hasattr(v, "isNull") and v.isNull():
            return None
    except Exception:
        pass
    for meth in ("toPyDateTime", "toPyDate"):
        f = getattr(v, meth, None)
        if callable(f):
            try:
                v = f()
                break
            except Exception:
                return None
    if isinstance(v, _dt.datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, _dt.date):
        return _dt.datetime(v.year, v.month, v.day)
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        if math.isnan(x) or x <= 0:
            return None
        if 19000101 <= x <= 21001231 and float(int(x)) == x:
            return _mk(int(x) // 10000, int(x) // 100 % 100, int(x) % 100)
        if 1 <= x < 80000:                       # serial Excel (1900 date system)
            return _dt.datetime(1899, 12, 30) + _dt.timedelta(days=x)
        if x > 1e11:                             # epoch milidetik
            x /= 1000.0
        try:
            return _dt.datetime(1970, 1, 1) + _dt.timedelta(seconds=x)
        except OverflowError:
            return None
    s = str(v).strip()
    if not s or s.upper() in ("NULL", "NONE", "NAN", "-", "0", "N/A", "NA"):
        return None
    m = _RX_ISO.match(s)
    if m:
        return _mk(*m.groups())
    m = _RX_8.match(s)
    if m:
        return _mk(*m.groups())
    m = _RX_DMY.match(s)
    if m:
        a, b, y, h, mi, sec = m.groups()
        a, b = int(a), int(b)
        if a > 12 >= b:
            d, mo = a, b
        elif b > 12 >= a:
            d, mo = b, a
        else:
            d, mo = (a, b) if dayfirst else (b, a)
        return _mk(y, mo, d, h, mi, sec)
    m = _RX_NAMA.match(s)
    if m and m.group(2).lower() in _BULAN:
        return _mk(m.group(3), _BULAN[m.group(2).lower()], m.group(1))
    m = _RX_NAMA2.match(s)
    if m and m.group(1).lower() in _BULAN:
        return _mk(m.group(3), _BULAN[m.group(1).lower()], m.group(2))
    try:
        if re.match(r"^-?\d+(\.\d+)?$", s):
            return _parse_date_raw(float(s), dayfirst)
    except ValueError:
        pass
    return None


# ------------------------------------------------------------------------------------------------ geometri dasar
def seg_len(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def line_len(pts):
    return sum(seg_len(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def proj_seg(p, a, b):
    """Titik terdekat pada segmen ab dari p -> (jarak, t[0..1], (x, y))."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    if l2 <= 0.0:
        return seg_len(p, a), 0.0, (a[0], a[1])
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    q = (a[0] + t * dx, a[1] + t * dy)
    return seg_len(p, q), t, q


def clean_line(pts, eps=1e-9):
    """Buang verteks berurutan yang sama."""
    out = []
    for p in pts:
        p = (float(p[0]), float(p[1]))
        if not out or seg_len(out[-1], p) > eps:
            out.append(p)
    return out


def point_at(pts, cum, m):
    """Titik pada ukuran (jarak sepanjang garis) m; cum = jarak kumulatif tiap verteks."""
    if m <= 0:
        return pts[0], 0
    if m >= cum[-1]:
        return pts[-1], len(pts) - 2
    lo, hi = 0, len(cum) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cum[mid] <= m:
            lo = mid
        else:
            hi = mid
    a, b = pts[lo], pts[lo + 1]
    L = cum[lo + 1] - cum[lo]
    t = (m - cum[lo]) / L if L > 0 else 0.0
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])), lo


def cumlen(pts):
    c = [0.0]
    for i in range(len(pts) - 1):
        c.append(c[-1] + seg_len(pts[i], pts[i + 1]))
    return c


def substring(pts, cum, m0, m1):
    """Potongan garis dari ukuran m0 ke m1 (m0 < m1) dengan verteks asli di antaranya."""
    p0, i0 = point_at(pts, cum, m0)
    p1, i1 = point_at(pts, cum, m1)
    out = [p0]
    for k in range(i0 + 1, i1 + 1):
        if cum[k] > m0 and cum[k] < m1:
            out.append(pts[k])
    out.append(p1)
    return clean_line(out)


def seg_intersection(a, b, c, d, eps=1e-12):
    """Titik potong segmen ab dan cd -> (t_ab, t_cd, (x, y)) atau None (sejajar/tidak bertemu)."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < eps:
        return None
    qp = (c[0] - a[0], c[1] - a[1])
    t = (qp[0] * s[1] - qp[1] * s[0]) / den
    u = (qp[0] * r[1] - qp[1] * r[0]) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return t, u, (a[0] + t * r[0], a[1] + t * r[1])
    return None


class SegIndex:
    """Indeks grid sederhana untuk segmen garis (cukup cepat untuk puluhan ribu segmen tanpa paket tambahan)."""

    def __init__(self, cell):
        self.cell = max(float(cell), 1e-6)
        self.g = {}
        self.segs = []          # (owner, line_idx, seg_idx, a, b)

    def _cells(self, x0, y0, x1, y1):
        c = self.cell
        for i in range(int(math.floor(min(x0, x1) / c)), int(math.floor(max(x0, x1) / c)) + 1):
            for j in range(int(math.floor(min(y0, y1) / c)), int(math.floor(max(y0, y1) / c)) + 1):
                yield (i, j)

    def _seg_cells(self, a, b):
        """Sel yang dilalui segmen (sel kotak pembatas tiap potongan sepanjang <= 1 sel; superset sel yang dilintasi).
        Jauh lebih hemat memori daripada seluruh kotak pembatas segmen panjang/diagonal, dan tetap lengkap: setiap
        titik segmen berada di salah satu sel terdaftar."""
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(math.ceil(L / self.cell)))
        seen = set()
        px, py = a
        for s in range(1, n + 1):
            f = s / n
            qx, qy = (b[0], b[1]) if s == n else (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            for key in self._cells(px, py, qx, qy):
                if key not in seen:
                    seen.add(key)
                    yield key
            px, py = qx, qy

    def add_line(self, owner, line_idx, pts):
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            sid = len(self.segs)
            self.segs.append((owner, line_idx, k, a, b))
            for key in self._seg_cells(a, b):
                self.g.setdefault(key, []).append(sid)

    def near(self, p, r):
        seen = set()
        for key in self._cells(p[0] - r, p[1] - r, p[0] + r, p[1] + r):
            for sid in self.g.get(key, ()):
                if sid not in seen:
                    seen.add(sid)
                    yield sid

    def nearest(self, p, r, skip=None):
        """Segmen terdekat dalam radius r -> (jarak, sid, t, q) atau None. skip(owner, line_idx) -> abaikan."""
        best = None
        for sid in self.near(p, r):
            owner, li, k, a, b = self.segs[sid]
            if skip is not None and skip(owner, li):
                continue
            d, t, q = proj_seg(p, a, b)
            if d <= r and (best is None or d < best[0] or (d == best[0] and sid < best[1])):
                best = (d, sid, t, q)       # seri jarak -> segmen terdaftar lebih dulu (tidak bergantung susunan sel)
        return best

    def boxed(self, a, b, r=0.0):
        seen = set()
        for key in self._cells(min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r):
            for sid in self.g.get(key, ()):
                if sid not in seen:
                    seen.add(sid)
                    yield sid



# ------------------------------------------------------------------------------------------------ pencocokan ke jalan
# Toleransi per sisi (jarak garis kabel ke garis tengah jalan, m) menurut kelas jalan OSM = setengah RUMIJA tipikal +
# margin digitasi. RUMIJA minimum PP 34/2006 Pasal 40: jalan bebas hambatan 30, raya 25, sedang 15, kecil 11 m;
# Permen PUPR 5/2023: jalan raya berjalur ganda s.d. 36 m. Jalan tol tidak digabung otomatis (kabel jarang sejajar).
ROAD_TOL = {"trunk": 22.0, "primary": 22.0, "secondary": 16.0, "tertiary": 13.0, "unclassified": 10.0,
            "residential": 10.0, "road": 10.0, "trunk_link": 8.0, "primary_link": 8.0, "secondary_link": 8.0,
            "tertiary_link": 8.0, "living_street": 6.0, "service": 6.0, "pedestrian": 6.0, "track": 5.0, "path": 5.0,
            "footway": 5.0}
ROAD_ANGLE = 30.0       # derajat; arah garis kabel vs arah ruas jalan (Walter & Fritsch 1999: sebagian besar < 10-30)


def _ang_diff(a, b):
    d = abs((a - b + math.pi) % (2.0 * math.pi) - math.pi)
    return min(d, math.pi - d)


class RoadMatcher:
    """Mencocokkan titik garis kabel ke garis tengah jalan terdekat (map matching geometris) dan menyimpan 'jejak'
    garis yang sudah dipakai sebagai titik proyeksi di jalan (linear referencing sederhana). Dua garis di dua sisi
    jalan yang sama memproyeksikan ke tempat yang sama di garis tengah jalan -> dianggap satu jalur, walaupun jaraknya
    lebih dari toleransi koridor. Gang/jalan sejajar adalah ruas lain -> tidak digabung (aturan jalan terdekat).

    roads: iterabel [(pts, kelas_osm, label, satu_arah)] dalam koordinat meter yang sama dengan garis kabel.
    Penyimpanan memakai array ringkas (jutaan ruas jalan tetap hemat memori)."""

    WALK = ("footway", "path", "pedestrian")

    def __init__(self, roads, cell=25.0, fp_cell=10.0, near_cells=None):
        """near_cells: himpunan sel (ukuran cell) di sekitar garis kabel; ruas jalan di luar sel ini diabaikan."""
        self.cell, self.fp_cell = cell, fp_cell
        A = lambda t: array(t)
        self.ax, self.ay, self.bx, self.by = A("d"), A("d"), A("d"), A("d")
        self.tol, self.ang = A("f"), A("f")
        self.lab, self.ow, self.walk = A("i"), A("b"), A("b")
        self.labels, lab_id = [], {}
        self.g = {}
        ends = {}           # titik ujung ruas (dibulatkan 0,5 m) -> [(label_id, sudut_keluar, tol)]
        for pts, cls, label, oneway in roads:
            tol = ROAD_TOL.get(cls)
            if tol is None or len(pts) < 2:
                continue
            li = lab_id.get(label)
            if li is None:
                li = lab_id[label] = len(self.labels)
                self.labels.append(label)
            for p0, p1 in ((pts[0], pts[1]), (pts[-1], pts[-2])):
                if p0 != p1:
                    ends.setdefault((round(p0[0] * 2.0), round(p0[1] * 2.0)), []).append(
                        (li, math.atan2(p1[1] - p0[1], p1[0] - p0[0]), tol))
            for k in range(len(pts) - 1):
                a, b = pts[k], pts[k + 1]
                if a == b:
                    continue
                cells = list(self._cells(a, b, 0.0, cell))
                if near_cells is not None and not any(c in near_cells for c in cells):
                    continue
                sid = len(self.ax)
                self.ax.append(a[0]); self.ay.append(a[1]); self.bx.append(b[0]); self.by.append(b[1])
                self.tol.append(tol); self.ang.append(math.atan2(b[1] - a[1], b[0] - a[0]))
                self.lab.append(li); self.ow.append(1 if oneway else 0); self.walk.append(1 if cls in self.WALK else 0)
                for key in cells:
                    lst = self.g.get(key)
                    if lst is None:
                        lst = self.g[key] = array("i")
                    lst.append(sid)
        n = len(self.ax)
        self.maxtol = max(self.tol) if n else 0.0
        self.dead = bytearray(n)

        def near_parallel(i, radius, pred):
            mid = ((self.ax[i] + self.bx[i]) / 2.0, (self.ay[i] + self.by[i]) / 2.0)
            seen = set()
            for key in self._cells(mid, mid, radius, cell):
                for j in self.g.get(key, ()):
                    if j == i or j in seen:
                        continue
                    seen.add(j)
                    if not pred(j) or _ang_diff(self.ang[i], self.ang[j]) > math.radians(20.0):
                        continue
                    d, _t, _q = proj_seg(mid, (self.ax[j], self.ay[j]), (self.bx[j], self.by[j]))
                    if d <= radius:
                        yield j, d
        # 1) Trotoar: footway/path di dalam koridor jalan kendaraan yang sejajar bukan jalur tersendiri (di OSM
        #    trotoar sering digambar terpisah); bila dibiarkan, kabel di dua sisi jalan menempel ke trotoar berbeda.
        self.n_sidewalk = 0
        for i in range(n):
            if self.walk[i]:
                for j, d in near_parallel(i, 10.0, lambda x: not self.walk[x]):
                    if d <= self.tol[j] * 0.6:
                        self.dead[i] = 1
                        self.n_sidewalk += 1
                        break
        # 2) Jalur ganda bermedian: dua ruas satu arah sejajar sekelas (<= 40 m) = satu jalan, walaupun tanpa nama
        #    atau bernama berbeda (ArcGIS Merge Divided Roads).
        parent = list(range(len(self.labels)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        # 3) Stroke (Thomson & Richardson 1999): ruas yang bersambung lurus (sudut <= 20 derajat) dengan kelas sama
        #    adalah jalan yang sama walaupun namanya berganti di persimpangan.
        for lst in ends.values():
            for x in range(len(lst)):
                for y in range(x + 1, len(lst)):
                    (la, aa, ta), (lb, ab, tb) = lst[x], lst[y]
                    if ta == tb and abs((aa - ab) % (2.0 * math.pi) - math.pi) <= math.radians(20.0):
                        ra, rb = find(la), find(lb)
                        if ra != rb:
                            parent[max(ra, rb)] = min(ra, rb)
        ends = None
        for i in range(n):
            if not self.ow[i] or self.dead[i]:
                continue
            for j, _d in near_parallel(i, 40.0, lambda x, t=self.tol[i]: self.ow[x] and self.tol[x] == t):
                la, lb = find(self.lab[i]), find(self.lab[j])
                if la != lb:
                    parent[max(la, lb)] = min(la, lb)
        self.n_dual = 0
        for i in range(n):
            r = find(self.lab[i])
            if r != self.lab[i]:
                self.lab[i] = r
                self.n_dual += 1
        self.n_labels = len({self.lab[i] for i in range(n) if not self.dead[i]})
        # jejak garis terpilih (array ringkas)
        self.fqx, self.fqy, self.fpx, self.fpy = A("d"), A("d"), A("d"), A("d")
        self.flab, self.fown, self.fli = A("i"), A("q"), A("i")
        self.fp = {}
        self.coarse = set()         # sel 50 m yang berisi jejak (penyaring cepat)
        self._cache = {}

    @staticmethod
    def _cells(a, b, r, c):
        for i in range(int(math.floor((min(a[0], b[0]) - r) / c)), int(math.floor((max(a[0], b[0]) + r) / c)) + 1):
            for j in range(int(math.floor((min(a[1], b[1]) - r) / c)), int(math.floor((max(a[1], b[1]) + r) / c)) + 1):
                yield (i, j)

    def __len__(self):
        return len(self.ax)

    def reset(self):
        """Kosongkan jejak (dipakai ulang untuk grup lain)."""
        for arr in (self.fqx, self.fqy, self.fpx, self.fpy, self.flab, self.fown, self.fli):
            del arr[:]
        self.fp, self.coarse = {}, set()

    def match(self, p, ang):
        """-> (label_id, titik_proyeksi, satu_arah) atau None. Ruas terdekat harus berada dalam toleransi kelasnya dan
        searah (selisih <= ROAD_ANGLE); bila ruas terdekat tidak memenuhi, tidak dicocokkan (konservatif)."""
        if not len(self.ax):
            return None
        ck = (int(math.floor(p[0] * 2.0)), int(math.floor(p[1] * 2.0)),
              None if ang is None else int(math.floor((ang % math.pi) / 0.1)))
        hit = self._cache.get(ck, 0)
        if hit != 0:
            if hit is None:
                return None
            label, qx, qy, oneway = hit
            return label, (qx, qy), oneway
        res = self._match(p, ang)
        if len(self._cache) > 400000:
            self._cache.clear()
        self._cache[ck] = None if res is None else (res[0], res[1][0], res[1][1], res[2])
        return res

    def _match(self, p, ang):
        best = None
        seen = set()
        for key in self._cells(p, p, self.maxtol, self.cell):
            for sid in self.g.get(key, ()):
                if sid in seen or self.dead[sid]:
                    continue
                seen.add(sid)
                d, _t, q = proj_seg(p, (self.ax[sid], self.ay[sid]), (self.bx[sid], self.by[sid]))
                if d > self.maxtol:
                    continue
                # seri jarak (mis. titik tepat di simpul pertemuan dua ruas) diputus menurut geometri ruas, bukan
                # urutan data jalan -> hasil sama apa pun sumber/urutan data jalan (uji: paket petak = GeoPackage)
                if best is None or d < best[0] - 1e-9 or (abs(d - best[0]) <= 1e-9 and self._gkey(sid) < self._gkey(best[1])):
                    best = (d, sid, q)
        if best is None:
            return None
        d, sid, q = best
        if d > self.tol[sid] or (ang is not None and _ang_diff(ang, self.ang[sid]) > math.radians(ROAD_ANGLE)):
            return None
        return self.lab[sid], q, bool(self.ow[sid])

    def _gkey(self, sid):
        a, b = (self.ax[sid], self.ay[sid]), (self.bx[sid], self.by[sid])
        return (a, b) if a <= b else (b, a)

    def add(self, owner, li, pts, step=8.0):
        """Daftarkan jejak potongan garis yang sudah dipakai (titik proyeksi tiap step m)."""
        if not len(self.ax) or len(pts) < 2:
            return
        cum = cumlen(pts)
        n = max(1, int(math.ceil(cum[-1] / step)))
        for i in range(n + 1):
            m = cum[-1] * i / n
            p, k = point_at(pts, cum, m)
            a, b = pts[min(k, len(pts) - 2)], pts[min(k, len(pts) - 2) + 1]
            mt = self.match(p, math.atan2(b[1] - a[1], b[0] - a[0]))
            if mt is None:
                continue
            q = mt[1]
            idx = len(self.fqx)
            self.fqx.append(q[0]); self.fqy.append(q[1]); self.fpx.append(p[0]); self.fpy.append(p[1])
            self.flab.append(mt[0]); self.fown.append(owner); self.fli.append(li)
            key = (int(math.floor(q[0] / self.fp_cell)), int(math.floor(q[1] / self.fp_cell)))
            lst = self.fp.get(key)
            if lst is None:
                lst = self.fp[key] = array("i")
            lst.append(idx)
            self.coarse.add((int(math.floor(q[0] / 50.0)), int(math.floor(q[1] / 50.0))))

    def nearest_fp(self, q, label, r, exclude=None):
        best = None
        for key in self._cells(q, q, r, self.fp_cell):
            for idx in self.fp.get(key, ()):
                if self.flab[idx] != label or (exclude is not None and self.fown[idx] == exclude):
                    continue
                d = math.hypot(self.fqx[idx] - q[0], self.fqy[idx] - q[1])
                if d <= r and (best is None or d < best[0]):
                    best = (d, idx)
        return None if best is None else best[1]

    def covered(self, p, ang):
        """Titik p tertutup garis lain yang mengikuti jalan yang sama di posisi yang sama -> (owner, titik_garis_itu,
        li) atau None. Jalan satu arah (jalur ganda bermedian) boleh berpasangan dengan jalur seberangnya sampai 30 m."""
        if not self.fp:
            return None
        cx, cy = int(math.floor(p[0] / 50.0)), int(math.floor(p[1] / 50.0))
        if not any((cx + dx, cy + dy) in self.coarse for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            return None
        mt = self.match(p, ang)
        if mt is None:
            return None
        label, q, oneway = mt
        idx = self.nearest_fp(q, label, ONEWAY_PAIR if oneway else 8.0)
        if idx is None:
            return None
        return self.fown[idx], (self.fpx[idx], self.fpy[idx]), self.fli[idx]


# ------------------------------------------------------------------------------------------------ status
DIPAKAI = "DIPAKAI"            # dipakai utuh sebagai bagian untai
DIPANGKAS = "DIPANGKAS"        # sebagian dipakai, bagian yang paralel dengan garis prioritas lebih tinggi dibuang
DUPLIKAT = "DUPLIKAT"          # seluruhnya (>= ambang) sudah terwakili garis lain di koridor yang sama
KOSONG = "GEOMETRI_KOSONG"     # tanpa geometri / panjang nol
SERPIHAN = "SERPIHAN"          # sisa tidak tertutup terlalu pendek (lebih pendek dari panjang potongan minimum)

MODE_PANGKAS, MODE_UTUH, MODE_SEMUA = 0, 1, 2


def _id(x, d=1):
    """Angka gaya Indonesia (koma desimal) untuk teks alasan."""
    return ("%%.%df" % d % x).replace(".", ",")


def geom_tie(parts, q=1e-3):
    """Kunci geometri kanonik (titik awal/akhir tiap bagian, dibulatkan 1 mm, arah dinormalkan). Dipakai sebagai
    pemutus seri sebelum FID, sehingga pilihan di antara garis bertanggal & berpanjang sama tidak bergantung pada
    urutan fitur di berkas (FID berubah bila data dipotong/digabung per wilayah)."""
    out = []
    for p in parts:
        a = (round(p[0][0] / q), round(p[0][1] / q))
        b = (round(p[-1][0] / q), round(p[-1][1] / q))
        out.append((a, b) if a <= b else (b, a))
    return tuple(sorted(out))


def priority_key(date, length, fid, newest_first=False, tie=()):
    """Kunci urut: tanggal tertua dulu (atau terbaru dulu), tanggal kosong selalu terakhir, lalu terpanjang, lalu
    pemutus seri yang tidak bergantung urutan berkas (geometri, lalu atribut), terakhir FID."""
    if date is None:
        dk = (1, 0.0)
    else:
        ts = (date - _dt.datetime(1900, 1, 1)).total_seconds()
        dk = (0, -ts if newest_first else ts)
    return (dk, -round(length, 6), tie, fid)


class Record:
    __slots__ = ("fid", "parts", "date", "group", "length", "key", "status", "dup_of", "cover", "kept_len",
                 "pieces", "rank", "note", "owners", "len_e", "kept_e", "road_len")

    def __init__(self, fid, parts, date=None, group=None, newest_first=False, uid=""):
        self.fid = fid
        self.parts = [p for p in (clean_line(pp) for pp in parts) if len(p) >= 2]
        self.date = date
        self.group = group
        self.length = sum(line_len(p) for p in self.parts)
        self.key = priority_key(date, self.length, fid, newest_first, (geom_tie(self.parts), str(uid or "")))
        self.status = None
        self.dup_of = None
        self.cover = 0.0
        self.kept_len = 0.0
        self.pieces = []        # [(pts, join_start(bool), join_end(bool))]
        self.rank = None
        self.note = ""
        self.owners = {}
        self.len_e = self.length
        self.kept_e = 0.0
        self.road_len = 0.0


def _sample(pts, step):
    cum = cumlen(pts)
    L = cum[-1]
    n = max(1, int(math.ceil(L / step)))
    ms = [L * i / n for i in range(n + 1)]
    return cum, ms, [point_at(pts, cum, m)[0] for m in ms]


def corridor_select(records, tol, min_cover=0.8, mode=MODE_PANGKAS, min_piece=None, step=None, drift=None,
                    road=None):
    """Langkah 1-2: pilih garis per koridor. records diurutkan menurut key; hasil diisi ke tiap Record.

    tol       : lebar setengah koridor (m) - garis yang berjarak <= tol dianggap satu koridor.
    min_cover : ambang cakupan (0..1) untuk menyatakan garis DUPLIKAT.
    mode      : MODE_PANGKAS (buang bagian paralel, sambung sisanya), MODE_UTUH (pakai utuh bila bukan duplikat),
                MODE_SEMUA (seperti skrip panduan: hanya buang yang identik, lalu gabung semua).
    road      : RoadMatcher opsional - garis yang mengikuti jalan yang sama di posisi yang sama (mis. kabel di dua sisi
                jalan) juga dianggap satu koridor, walaupun jaraknya > tol.
    """
    if mode == MODE_SEMUA:
        road = None
    tol = float(tol)
    if mode == MODE_SEMUA:
        tol_eff, min_cover = 0.01, 0.999
    else:
        tol_eff = max(tol, 1e-6)
    step = step or max(0.2, min(tol_eff / 2.0, 2.0))
    if min_piece is None:
        min_piece = max(2.0 * tol_eff, 1.0)
    end_keep = min(0.5, min_piece)        # ekor lebih pendek dari 0,5 m dianggap derau digitasi
    drift_tol = max(drift or 2.0 * tol_eff, tol_eff)   # pita drift: bawaan 2 x toleransi (5 m < badan jalan 5,5 m)
    idx = SegIndex(max(tol_eff * 4.0, 5.0))
    # 'Bayangan': bagian garis lama yang sudah dinilai drift (koridor yang sama dengan garis yang lebih tua lagi).
    # Garis yang lebih baru di atas bayangan ikut dianggap tertutup, sehingga garis baru tidak mewakili tempat yang
    # sudah diputuskan milik garis tertua (temuan uji Bangka Belitung v1.2: 0,08% titik).
    ghost = SegIndex(max(tol_eff * 4.0, 5.0))
    ghost_n = [0]
    accepted = {}            # fid -> list of pts (potongan yang dipakai)
    rank_of = {}
    order = sorted(records, key=lambda r: r.key)
    for rank, rec in enumerate(order, 1):
        rec.rank = rank
        if rec.length <= 0:
            rec.status, rec.note = KOSONG, "tanpa geometri garis"
            continue
        covered_len = 0.0
        road_len = 0.0
        owners = {}
        part_info = []
        for pts in rec.parts:
            cum, ms, smp = _sample(pts, step)
            cov = []
            for si, p in enumerate(smp):
                hit = idx.nearest(p, tol_eff)
                if hit is None and road is not None:
                    a_, b_ = (smp[si], smp[si + 1]) if si + 1 < len(smp) else (smp[si - 1], smp[si])
                    rh = road.covered(p, math.atan2(b_[1] - a_[1], b_[0] - a_[0])) if a_ != b_ else None
                    if rh is not None:
                        cov.append((rh[0], rh[1], rh[2], True))
                        continue
                if hit is None and ghost_n[0] and ghost.nearest(p, tol_eff) is not None:
                    hit = idx.nearest(p, drift_tol)
                    if hit is None:
                        cov.append((None, p, -1))      # tertutup bayangan, tanpa titik sambung
                        continue
                if hit is None:
                    cov.append(None)
                else:
                    owner, li = idx.segs[hit[1]][0], idx.segs[hit[1]][1]
                    cov.append((owner, hit[3], li))
            if road is not None:
                _fill_road_gaps(cov, ms, ROAD_FILL)
            for i in range(len(ms) - 1):
                if cov[i] is not None and cov[i + 1] is not None:
                    dl = ms[i + 1] - ms[i]
                    covered_len += dl
                    if len(cov[i]) > 3 or len(cov[i + 1]) > 3:
                        road_len += dl
                    if cov[i][0] is not None:
                        owners[cov[i][0]] = owners.get(cov[i][0], 0.0) + dl
            part_info.append((pts, cum, ms, cov, smp))
        rec.cover = covered_len / rec.length if rec.length else 0.0
        rec.road_len = road_len
        rec.owners = owners
        if owners and rec.cover >= 0.01:
            rec.dup_of = max(owners.items(), key=lambda kv: (kv[1], -rank_of.get(kv[0], 0)))[0]
        rank_of[rec.fid] = rank
        links = _connectors(part_info, accepted, tol_eff) if mode != MODE_SEMUA else []
        dup_note = "%s%% panjang berada dalam koridor %s m dari garis FID %s" % (
            _id(rec.cover * 100, 0), _id(tol_eff, 2), rec.dup_of)
        if road_len > 0:
            dup_note = "%s%% panjang mengikuti jalur yang sama dengan garis FID %s (%s m di antaranya di sisi lain " \
                       "jalan yang sama)" % (_id(rec.cover * 100, 0), rec.dup_of, _id(road_len))
        if mode != MODE_PANGKAS:
            # mode utuh / gabung semua: garis dipakai utuh kecuali hampir seluruhnya (>= ambang) sudah terwakili
            if rec.cover >= min_cover - 1e-9:
                rec.status, rec.note = DUPLIKAT, dup_note
                if links:
                    _use_links(rec, links, dup_note)
            else:
                rec.pieces = [(list(p[0]), False, False) for p in part_info]
                rec.kept_len = rec.length
                rec.status = DIPAKAI
                if rec.cover >= 0.01:
                    rec.note = "dipakai utuh; %s%% sejajar dengan FID %s" % (_id(rec.cover * 100, 0), rec.dup_of)
        elif covered_len < min_piece:
            # hampir tidak bersinggungan (mis. hanya bersilangan): dipakai utuh, kecuali bagian yang seluruhnya
            # berjalan di pita drift di samping garis terpilih
            keep, drift_len = [], 0.0
            for pts, cum, ms, cov, smp in part_info:
                if _drift(smp, cov, idx, accepted, drift_tol):
                    drift_len += cum[-1]
                    ghost.add_line(rec.fid, len(keep), pts)
                    ghost_n[0] += 1
                else:
                    keep.append((list(pts), False, False))
            if not keep:
                rec.status = DUPLIKAT
                rec.note = "seluruhnya sejajar dalam pita drift %s m dari garis FID %s" % (
                    _id(drift_tol, 1), _drift_owner(part_info, idx, drift_tol))
                rec.dup_of = rec.dup_of or _drift_owner(part_info, idx, drift_tol)
                if links:
                    _use_links(rec, links, rec.note)
            else:
                rec.pieces = keep
                rec.kept_len = sum(line_len(p[0]) for p in keep)
                rec.status = DIPAKAI if drift_len == 0 else DIPANGKAS
                if drift_len > 0:
                    rec.note = "sisa drift %s m dalam pita %s m dibuang" % (_id(drift_len), _id(drift_tol, 1))
                elif rec.cover >= 0.01:
                    rec.note = "dipakai utuh; %s%% sejajar dengan FID %s" % (_id(rec.cover * 100, 0), rec.dup_of)
        else:
            # Mode pangkas: SETIAP sisa di luar koridor dipertahankan berapa pun persen cakupannya, sehingga tidak
            # ada jalur unik yang hilang (temuan uji Bangka Belitung: ambang 80% membuang 17 km jalur unik).
            pieces = []
            drift_len = 0.0
            for pts, cum, ms, cov, smp in part_info:
                n = len(ms)
                i = 0
                while i < n - 1:
                    if cov[i] is not None and cov[i + 1] is not None:
                        i += 1
                        continue
                    j = i
                    while j < n - 1 and not (cov[j] is not None and cov[j + 1] is not None):
                        j += 1
                    m0, m1 = ms[i], ms[j]
                    # Sisa pendek di ANTARA dua bagian tertutup = serpihan zig-zag (dibuang). Sisa yang menyentuh
                    # ujung asli garis = perpanjangan/ekor jalur: tetap dipakai walau pendek, karena membuangnya
                    # memutus untai (temuan uji data Bangka Belitung).
                    touches_end = (i == 0) or (j == n - 1)
                    if m1 - m0 >= min_piece or (touches_end and m1 - m0 > end_keep):
                        sub = substring(pts, cum, m0, m1)
                        js = cov[i] is not None and cov[i][0] is not None
                        je = cov[j] is not None and cov[j][0] is not None
                        # Batas yang tertutup lewat aturan jalan berada di SEBERANG jalan: penyambung ke sana akan
                        # melintang jalan (anak tangga). Tidak disambung bila lebih jauh dari toleransi; jalurnya
                        # tetap utuh lewat garis di sisi seberang.
                        # Cabang yang keluar dari jalan (penyambung segaris dengan arah potongan, <= 45 derajat)
                        # tetap disambung: kabelnya memang menyeberang jalan di situ.
                        if js and len(cov[i]) > 3 and seg_len(cov[i][1], sub[0]) > tol_eff and \
                                not _straight(cov[i][1], sub[0], _ahead(sub, 0)):
                            js = False
                        if je and len(cov[j]) > 3 and seg_len(cov[j][1], sub[-1]) > tol_eff and \
                                not _straight(cov[j][1], sub[-1], _ahead(sub, -1)):
                            je = False
                        # Sambungan ke garis pemilik koridor DITAMBAHKAN sebagai verteks baru (<= toleransi), bukan
                        # menggeser ujung asli: menggeser ujung potongan dua-verteks memindahkan seluruh ruasnya ke
                        # atas garis pemilik (temuan uji Bangka Belitung v1.1: tumpukan baru sampai 103 m).
                        if js:
                            sub = [cov[i][1]] + sub
                        if je:
                            sub = sub + [cov[j][1]]
                        sub = clean_line(sub)
                        # Pita drift: sisa yang SELURUH titiknya tetap <= 2 x toleransi dari garis terpilih dan
                        # berjalan di sampingnya (kaki tegak lurus di badan garis, bukan di ujungnya) adalah jalur
                        # yang sama dengan selisih digitasi > toleransi - kabel di seberang jalan berjarak >= lebar
                        # badan jalan 5,5 m. Dibuang. Ekor yang memanjang melewati ujung garis tetap dipakai.
                        if _drift(smp[i:j + 1], cov[i:j + 1], idx, accepted, drift_tol):
                            drift_len += line_len(sub)
                            ghost.add_line(rec.fid, 0, sub)
                            ghost_n[0] += 1
                        elif len(sub) >= 2:
                            pieces.append((sub, js, je))
                    i = j
            uniq = sum(line_len(p[0]) for p in pieces)
            if not pieces:
                rec.status, rec.note = DUPLIKAT, dup_note
                if drift_len > 0:
                    rec.note += " (sisa drift %s m dalam pita %s m dibuang)" % (_id(drift_len), _id(drift_tol, 1))
                if links:
                    _use_links(rec, links, dup_note)
            else:
                pieces.extend((lk[0], True, True) for lk in links)
                rec.pieces = pieces
                rec.kept_len = sum(line_len(p[0]) for p in pieces)
                rec.status = DIPANGKAS
                rec.note = "%s%% sejajar dengan FID %s dipangkas; %d potongan %s m di luar koridor dipakai" % (
                    _id(rec.cover * 100, 0), rec.dup_of, len(pieces), _id(uniq))
                if drift_len > 0:
                    rec.note += "; sisa drift %s m dalam pita %s m dibuang" % (_id(drift_len), _id(drift_tol, 1))
                if links:
                    rec.note += " + %d penyambung" % len(links)
        for k, (p, _js, _je) in enumerate(rec.pieces):
            idx.add_line(rec.fid, k, p)
            if road is not None:
                road.add(rec.fid, k, p, 8.0)
        accepted[rec.fid] = [p[0] for p in rec.pieces]
    return order, accepted


ROAD_FILL = 40.0
ONEWAY_PAIR = 45.0      # jalur seberang jalan berpemisah (lajur 2 x 7 m + median s.d. 20 m + bahu): proyeksi berjarak
                        # s.d. ~40 m; 30 m membuat cakupan putus-putus dan garis berpindah sisi (uji Soekarno-Hatta)     # m: celah cakupan pendek di antara dua bagian 'jalan yang sama' (persimpangan) ikut tertutup


def _ahead(pts, end, dist=10.0):
    """Titik pada potongan sejauh dist dari ujungnya (end 0 = awal, -1 = akhir)."""
    seq = pts if end == 0 else pts[::-1]
    acc = 0.0
    for k in range(len(seq) - 1):
        acc += seg_len(seq[k], seq[k + 1])
        if acc >= dist:
            return seq[k + 1]
    return seq[-1]


def _straight(a, b, c, max_deg=45.0):
    """a -> b -> c hampir lurus (belokan di b <= max_deg)."""
    ux, uy, vx, vy = b[0] - a[0], b[1] - a[1], c[0] - b[0], c[1] - b[1]
    nu, nv = math.hypot(ux, uy), math.hypot(vx, vy)
    if nu <= 0 or nv <= 0:
        return False
    return (ux * vx + uy * vy) / (nu * nv) >= math.cos(math.radians(max_deg))


def _fill_road_gaps(cov, ms, max_gap):
    """Di persimpangan, titik kabel bisa sesaat menempel ke jalan cabang sehingga cakupan 'jalan yang sama' terputus
    beberapa meter. Tanpa penanganan, potongan kecil + penyambung menyeberang jalan muncul sebagai kotak-kotak. Celah
    tak tertutup <= max_gap yang diapit dua titik tertutup (salah satunya lewat aturan jalan) dianggap tertutup."""
    n = len(cov)
    i = 0
    while i < n:
        if cov[i] is not None:
            i += 1
            continue
        j = i
        while j < n and cov[j] is None:
            j += 1
        if i > 0 and j < n and ms[j] - ms[i - 1] <= max_gap and (len(cov[i - 1]) > 3 or len(cov[j]) > 3):
            src = cov[i - 1] if len(cov[i - 1]) > 3 else cov[j]
            for k in range(i, j):
                cov[k] = (src[0], src[1], src[2], True)
        i = j


def _drift(samples, covs, idx, accepted, r):
    """True bila semua titik sampel yang TIDAK tertutup toleransi tetap <= r dari garis terpilih dan kaki tegak
    lurusnya jatuh di badan garis itu (bukan di ujungnya). Ekor yang memanjang melewati ujung garis = bukan drift."""
    seen = False
    for q, c in zip(samples, covs):
        if c is not None:
            continue
        seen = True
        hit = idx.nearest(q, r)
        if hit is None:
            return False
        d, sid, t, foot = hit
        owner, li, k, a, b = idx.segs[sid]
        pcs = accepted.get(owner) or []
        pts = pcs[li] if li < len(pcs) else None
        if pts is None:
            return False
        if (k == 0 and t <= 1e-6) or (k == len(pts) - 2 and t >= 1 - 1e-6):
            return False
    return seen


def _drift_owner(part_info, idx, r):
    """FID garis terpilih terdekat untuk sisa drift (untuk kolom 'duplikat dari')."""
    for pts, cum, ms, cov, smp in part_info:
        for q in smp:
            hit = idx.nearest(q, r)
            if hit is not None:
                return idx.segs[hit[1]][0]
    return None


def _within(pts, idx, r, step):
    """True bila setiap titik sampel garis berada <= r dari garis yang sudah diterima (Hausdorff berarah <= r)."""
    _cum, _ms, smp = _sample(pts, step)
    return all(idx.nearest(q, r) is not None for q in smp)


def _use_links(rec, links, note):
    """Garis duplikat yang menjadi satu-satunya penghubung dua garis terpilih yang tidak bersentuhan: hanya
    penyambungnya yang dipakai, agar untai tidak terputus (temuan uji data Bangka Belitung)."""
    rec.status = DIPANGKAS
    rec.pieces = [(lk[0], True, True) for lk in links]
    rec.kept_len = sum(line_len(lk[0]) for lk in links)
    rec.note = note + "; %d penyambung %s m dipakai antara FID %s" % (
        len(links), _id(rec.kept_len), ", ".join(sorted(set("%s-%s" % lk[1] for lk in links))))


def _dist_to_line(p, pts):
    return min(proj_seg(p, pts[k], pts[k + 1])[0] for k in range(len(pts) - 1))


def _touch(pa, pb, tol):
    """Dua potongan bersentuhan bila salah satu ujungnya berjarak <= tol dari potongan lain (akan disambung saat
    noding)."""
    return (min(_dist_to_line(pb[0], pa), _dist_to_line(pb[-1], pa)) <= tol or
            min(_dist_to_line(pa[0], pb), _dist_to_line(pa[-1], pb)) <= tol)


def _connectors(part_info, accepted, tol):
    """Penyambung: di titik garis kandidat berpindah 'pemilik koridor' dari potongan A ke potongan B yang tidak
    bersentuhan, dan salah satu titik proyeksinya dekat UJUNG potongannya (ada celah antar-ujung, bukan dua garis
    sejajar). Hasil: [(pts, (fidA, fidB))] - satu penyambung per pasangan potongan."""
    out, seen = [], set()
    join_tol = max(min(tol / 2.0, 1.0), 0.05)      # sama dengan toleransi sambung ujung bawaan
    for pts, cum, ms, cov, _smp in part_info:
        for i in range(len(cov) - 1):
            a, b = cov[i], cov[i + 1]
            if a is None or b is None or a[0] is None or b[0] is None or (a[0], a[2]) == (b[0], b[2]):
                continue
            pair = tuple(sorted(((a[0], a[2]), (b[0], b[2])), key=str))
            if pair in seen or seg_len(a[1], b[1]) <= 0.05:
                continue
            if (len(a) > 3 or len(b) > 3) and seg_len(a[1], b[1]) > tol:     # melintang jalan: bukan penyambung
                continue
            pa = accepted.get(a[0], [])
            pb = accepted.get(b[0], [])
            pa = pa[a[2]] if a[2] < len(pa) else None
            pb = pb[b[2]] if b[2] < len(pb) else None
            near_end = any(pp is not None and min(seg_len(q, pp[0]), seg_len(q, pp[-1])) <= tol
                           for q, pp in ((a[1], pa), (b[1], pb)))
            if not near_end or (pa is not None and pb is not None and _touch(pa, pb, join_tol)):
                continue
            seen.add(pair)
            out.append(([a[1], b[1]], (a[0], b[0])))
    return out


# ------------------------------------------------------------------------------------------------ noding + merge
def _key(p, q=1e-4):
    return (round(p[0] / q), round(p[1] / q))


def node_lines(lines, snap_tol=0.5, split_crossings=True):
    """Noding: sambungkan ujung yang hampir bertemu (<= snap_tol), tempel ujung ke badan garis lain (T),
    dan pecah garis di titik sambungan serta persilangan. lines: [(pts, owner)] -> [(pts, owner)]."""
    lines = [(clean_line(p), o) for p, o in lines]
    lines = [(p, o) for p, o in lines if len(p) >= 2 and line_len(p) > 0]
    if not lines:
        return []
    snap_tol = max(float(snap_tol), 1e-6)
    # 1) klaster ujung: jangkar = ujung dari garis yang lebih dulu (prioritas lebih tinggi)
    anchors = []
    grid = {}
    c = max(snap_tol * 2, 1e-3)

    def find_anchor(p):
        gi, gj = int(math.floor(p[0] / c)), int(math.floor(p[1] / c))
        best = None
        for i in (gi - 1, gi, gi + 1):
            for j in (gj - 1, gj, gj + 1):
                for a in grid.get((i, j), ()):
                    d = seg_len(p, anchors[a])
                    if d <= snap_tol and (best is None or d < best[0]):
                        best = (d, a)
        if best is not None:
            return anchors[best[1]]
        anchors.append(p)
        grid.setdefault((gi, gj), []).append(len(anchors) - 1)
        return p

    out = []
    for pts, o in lines:
        pts = list(pts)
        pts[0] = find_anchor(pts[0])
        pts[-1] = find_anchor(pts[-1])
        pts = clean_line(pts)
        if len(pts) >= 2 and line_len(pts) > 0:
            out.append((pts, o))
    lines = out
    # 2) titik pecah: ujung yang menempel di badan garis lain + persilangan
    idx = SegIndex(max(snap_tol * 4, 5.0))
    for li, (pts, o) in enumerate(lines):
        idx.add_line(o, li, pts)
    cuts = {}               # li -> list of (seg_idx, t, pt)

    def add_cut(li, k, t, q):
        cuts.setdefault(li, []).append((k, t, q))

    for li, (pts, o) in enumerate(lines):
        for end in (0, -1):
            p = pts[end]
            best = None
            for sid in idx.near(p, snap_tol):
                _o, lj, k, a, b = idx.segs[sid]
                if lj == li:
                    continue
                d, t, q = proj_seg(p, a, b)
                if d <= snap_tol and (best is None or (d, sid) < (best[0], best[5])):
                    best = (d, lj, k, t, q, sid)
            if best is None:
                continue
            d, lj, k, t, q = best[:5]
            tpts = lines[lj][0]
            # menempel di ujung garis lain -> sudah ditangani klaster ujung
            if (k == 0 and t <= 1e-9) or (k == len(tpts) - 2 and t >= 1 - 1e-9):
                continue
            pts[end] = q
            add_cut(lj, k, t, q)
    if split_crossings:
        for li, (pts, o) in enumerate(lines):
            for k in range(len(pts) - 1):
                a, b = pts[k], pts[k + 1]
                for sid in idx.boxed(a, b):
                    _o, lj, kk, c1, d1 = idx.segs[sid]
                    if lj <= li:
                        continue
                    hit = seg_intersection(a, b, c1, d1)
                    if hit is None:
                        continue
                    t, u, q = hit
                    a_end = (k == 0 and t <= 1e-9) or (k == len(pts) - 2 and t >= 1 - 1e-9)
                    b_end = (kk == 0 and u <= 1e-9) or (kk == len(lines[lj][0]) - 2 and u >= 1 - 1e-9)
                    if not a_end:
                        add_cut(li, k, t, q)
                    if not b_end:
                        add_cut(lj, kk, u, q)
    result = []
    for li, (pts, o) in enumerate(lines):
        cl = cuts.get(li)
        if not cl:
            result.append((pts, o))
            continue
        cl.sort(key=lambda x: (x[0], x[1]))
        cur = [pts[0]]
        ci = 0
        for k in range(len(pts) - 1):
            while ci < len(cl) and cl[ci][0] == k:
                q = cl[ci][2]
                if seg_len(cur[-1], q) > 1e-9:
                    cur.append(q)
                    if len(cur) >= 2:
                        result.append((clean_line(cur), o))
                    cur = [q]
                ci += 1
            cur.append(pts[k + 1])
        cur = clean_line(cur)
        if len(cur) >= 2:
            result.append((cur, o))
    return [(p, o) for p, o in result if len(p) >= 2 and line_len(p) > 1e-6]


def _dedupe_edges(lines):
    seen = {}
    out = []
    for pts, o in lines:
        a, b = _key(pts[0]), _key(pts[-1])
        mid = _key(pts[len(pts) // 2]) if len(pts) > 2 else None
        k = (min(a, b), max(a, b), round(line_len(pts), 2), mid if a <= b else mid)
        if k in seen:
            continue
        seen[k] = 1
        out.append((pts, o))
    return out


def _ow(o):
    return set(o) if isinstance(o, (set, frozenset)) else {o}


def merge_lines(lines):
    """Line merge: gabungkan rantai garis melalui simpul berderajat 2. lines: [(pts, owner)].
    Hasil: daftar rantai [(pts, set(owner))]."""
    lines = _dedupe_edges(lines)
    adj = {}
    for ei, (pts, o) in enumerate(lines):
        adj.setdefault(_key(pts[0]), []).append(ei)
        adj.setdefault(_key(pts[-1]), []).append(ei)
    used = [False] * len(lines)

    def other_end(ei, nk):
        pts = lines[ei][0]
        return _key(pts[-1]) if _key(pts[0]) == nk else _key(pts[0])

    def oriented(ei, nk):
        pts = lines[ei][0]
        return list(pts) if _key(pts[0]) == nk else list(reversed(pts))

    chains = []

    def walk(start_node, ei):
        pts = oriented(ei, start_node)
        owners = set(_ow(lines[ei][1]))
        used[ei] = True
        node = other_end(ei, start_node)
        while len(adj.get(node, ())) == 2:
            nxt = [e for e in adj[node] if not used[e]]
            if not nxt:
                break
            e = nxt[0]
            seg = oriented(e, node)
            pts.extend(seg[1:])
            owners |= _ow(lines[e][1])
            used[e] = True
            node = other_end(e, node)
        chains.append((clean_line(pts), owners))

    for nk, es in adj.items():
        if len(es) != 2:
            for ei in es:
                if not used[ei]:
                    walk(nk, ei)
    for ei in range(len(lines)):           # sisa: lingkaran tertutup
        if not used[ei]:
            walk(_key(lines[ei][0][0]), ei)
    return chains


def components(chains):
    """Kelompokkan rantai menjadi komponen tersambung (berbagi simpul)."""
    parent = list(range(len(chains)))

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    node_owner = {}
    for ci, (pts, _o) in enumerate(chains):
        for p in (pts[0], pts[-1]):
            k = _key(p)
            if k in node_owner:
                a, b = f(ci), f(node_owner[k])
                if a != b:
                    parent[a] = b
            else:
                node_owner[k] = ci
    groups = {}
    for ci in range(len(chains)):
        groups.setdefault(f(ci), []).append(ci)
    return sorted(groups.values(), key=lambda g: -sum(line_len(chains[c][0]) for c in g))


def node_degrees(chains):
    deg = {}
    for pts, _o in chains:
        for p in (pts[0], pts[-1]):
            k = _key(p)
            deg[k] = deg.get(k, 0) + 1
    return deg


HEADING_COS = 0.5          # cos 60 derajat


def heading_cos(prev, p, q):
    """Kosinus sudut antara arah keluar ujung garis (prev -> p) dan arah ke sasaran (p -> q)."""
    vx, vy = p[0] - prev[0], p[1] - prev[1]
    wx, wy = q[0] - p[0], q[1] - p[1]
    a, b = math.hypot(vx, vy), math.hypot(wx, wy)
    if a <= 0 or b <= 0:
        return 1.0
    return (vx * wx + vy * wy) / (a * b)


COLLINEAR_COS = math.cos(math.radians(30))   # >30 derajat = titik belok (tiang sudut wajib tambat)


def _chain_ident(chain, ident):
    if not ident:
        return set()
    return set(ident[o] for o in _ow(chain[1]) if o in ident and ident[o] not in (None, ""))


def find_gaps(chains, comps, radius, ident=None):
    """Celah (undershoot): ujung bebas (derajat 1) sebuah untai yang berhenti <= radius sebelum untai lain dan
    mengarah ke sana (sudut <= 60 derajat; ujung garis sejajar di seberang jalan bukan celah).
    Hasil per ujung bebas: (jarak, titik_ujung, titik_tujuan, comp_a, comp_b, jenis, sama_id), urut jarak.
      jenis  = 'SEGARIS' bila sasarannya juga ujung bebas yang menghadap balik dan kedua arah <= 30 derajat dari
               garis sambung (kelanjutan lurus jalur yang sama), selain itu 'T' (ujung menempel ke badan garis).
      sama_id = True bila kedua sisi berbagi nilai kolom identitas kabel (mis. NAME), None bila tidak dinilai."""
    if radius <= 0 or len(comps) < 2:
        return []
    comp_of = {}
    for gi, g in enumerate(comps):
        for ci in g:
            comp_of[ci] = gi
    idx = SegIndex(max(radius, 5.0))
    for ci, (pts, _o) in enumerate(chains):
        idx.add_line(comp_of[ci], ci, pts)
    deg = node_degrees(chains)
    out = []
    for ci, (pts, _o) in enumerate(chains):
        for p, prev in ((pts[0], pts[1]), (pts[-1], pts[-2])):
            if deg.get(_key(p), 0) != 1:
                continue
            ga = comp_of[ci]
            hit = idx.nearest(p, radius, skip=lambda owner, li, ga=ga: owner == ga)
            if hit is None:
                continue
            d, sid, t, q = hit
            ca = heading_cos(prev, p, q)
            if d > 1e-6 and ca < HEADING_COS:
                continue
            gb, cj = idx.segs[sid][0], idx.segs[sid][1]
            kind = "T"
            qp = chains[cj][0]
            for e, pr in ((qp[0], qp[1]), (qp[-1], qp[-2])):
                if (seg_len(e, q) <= 0.5 and deg.get(_key(e), 0) == 1 and ca >= COLLINEAR_COS and
                        heading_cos(pr, e, p) >= COLLINEAR_COS):
                    kind = "SEGARIS"
                    break
            same = None
            if ident:
                same = bool(_chain_ident(chains[ci], ident) & _chain_ident(chains[cj], ident))
            out.append((d, p, q, ga, gb, kind, same))
    out.sort(key=lambda x: x[0])
    return out


def unique_gaps(gaps):
    """Satu celah per pasangan untai (yang terpendek) untuk pelaporan."""
    best = {}
    for g in gaps:
        pair = (min(g[3], g[4]), max(g[3], g[4]))
        if pair not in best:
            best[pair] = g
    return sorted(best.values(), key=lambda x: x[0])


def bridge_ok(g, gap_tol, smart_tol, band=0.0):
    """Celah dijembatani bila <= gap_tol (semua jenis); atau <= smart_tol dan (segaris ATAU satu identitas kabel);
    atau (aturan cerdas aktif) ujungnya mengarah ke untai lain dalam pita drift - satu koridor, bukan jalur lain."""
    d, kind, same = g[0], g[5], g[6]
    return d <= gap_tol or (smart_tol > 0 and (d <= band or (d <= smart_tol and (kind == "SEGARIS" or same is True))))


def build_strands(pieces, snap_tol=0.5, gap_tol=0.0, gap_report=0.0, split_crossings=True, smart_tol=0.0,
                  ident=None, band=0.0):
    """Langkah 3-4. pieces: [(pts, owner_fid)]. Hasil dict: chains, comps, gaps (sebelum jembatan), bridges."""
    noded = node_lines(pieces, snap_tol, split_crossings)
    chains = merge_lines(noded)
    comps = components(chains)
    bridges = []
    gaps_all = find_gaps(chains, comps, max(gap_tol, smart_tol, gap_report), ident)
    if gap_tol > 0 or smart_tol > 0:
        # Hutan perentang minimum (Kruskal 1956): celah diurutkan dari yang terpendek, jembatan hanya dibuat bila
        # dua untai belum tersambung (union-find) dan ujung bebas itu belum dipakai. Satu kali noding untuk semua
        # jembatan, sehingga tetap cepat untuk ribuan celah.
        gaps = [g for g in gaps_all if g[0] > 1e-9 and bridge_ok(g, gap_tol, smart_tol, band)]
        if gaps:
            parent = list(range(len(comps)))

            def root(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i
            used_ends, new = set(), []
            for g in gaps:
                d, p, q, ga, gb = g[:5]
                ra, rb = root(ga), root(gb)
                if ra == rb or _key(p) in used_ends:
                    continue
                parent[ra] = rb
                used_ends.add(_key(p))
                used_ends.add(_key(q))
                bridges.append(g)
                new.append(([p, q], "JEMBATAN"))
            noded = node_lines([(c[0], frozenset(c[1])) for c in chains] + new,
                               max(snap_tol, 1e-3), split_crossings)
            chains = merge_lines(noded)
            comps = components(chains)
    return {"chains": chains, "comps": comps, "gaps": unique_gaps(gaps_all), "bridges": bridges}


def strand_summary(chains, comp):
    pts_list = [chains[c][0] for c in comp]
    owners = set()
    for c in comp:
        owners |= _ow(chains[c][1])
    owners.discard("JEMBATAN")
    deg = node_degrees([chains[c] for c in comp])
    ends = sum(1 for v in deg.values() if v == 1)
    junctions = sum(1 for v in deg.values() if v >= 3)
    return {"lines": pts_list, "owners": owners, "length": sum(line_len(p) for p in pts_list),
            "n_chain": len(pts_list), "ends": ends, "junctions": junctions,
            "closed": len(pts_list) == 1 and seg_len(pts_list[0][0], pts_list[0][-1]) < 1e-6}


def _near_cells(records, cell):
    """Sel grid (ukuran cell) yang dilalui garis-garis, diperlebar satu sel ke segala arah."""
    out = set()
    for r in records:
        for pts in r.parts:
            cum = cumlen(pts)
            n = max(1, int(math.ceil(cum[-1] / (cell / 2.0))))
            for i in range(n + 1):
                p, _k = point_at(pts, cum, cum[-1] * i / n)
                cx, cy = int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        out.add((cx + dx, cy + dy))
    return out


def consolidate(records, tol=3.0, min_cover=0.8, mode=MODE_PANGKAS, snap_tol=None, gap_tol=0.0, gap_report=None,
                min_piece=None, step=None, split_crossings=True, smart_tol=0.0, ident=None, drift=None, roads=None):
    """Jalankan seluruh proses per grup. Hasil: dict(order, groups={grup: build_strands(...)}, params)."""
    tol = float(tol)
    if snap_tol is None:
        snap_tol = max(min(tol / 2.0, 1.0), 0.05)
    if gap_report is None:
        gap_report = max(gap_tol, smart_tol, 10.0 * max(tol, 1.0))
    by_group = {}
    for r in records:
        by_group.setdefault(r.group, []).append(r)
    order_all = []
    groups = {}
    for g in sorted(by_group, key=lambda x: (x is None, str(x))):
        if isinstance(roads, RoadMatcher):
            rm = roads
            rm.reset()                      # jejak garis grup lain tidak berlaku
        else:
            rm = RoadMatcher(roads, near_cells=_near_cells(by_group[g], 25.0)) if roads else None
        order, accepted = corridor_select(by_group[g], tol, min_cover, mode, min_piece, step, drift, rm)
        order_all.extend(order)
        pieces = [(p[0], r.fid) for r in order for p in r.pieces]
        groups[g] = build_strands(pieces, snap_tol, gap_tol, gap_report, split_crossings, smart_tol, ident,
                                  max(drift or 2.0 * tol, tol) if mode == MODE_PANGKAS else 0.0)
    return {"order": order_all, "groups": groups,
            "params": {"tol": tol, "min_cover": min_cover, "mode": mode, "snap_tol": snap_tol, "gap_tol": gap_tol,
                       "gap_report": gap_report, "smart_tol": smart_tol,
                       "drift": max(drift or 2.0 * tol, tol)}}


# ------------------------------------------------------------------------------------------------ kelompok ruang
def spatial_clusters(boxes, pad_x, pad_y, cell=0.01):
    """Kelompokkan garis yang mungkin saling memengaruhi. boxes: {kunci: (minx, miny, maxx, maxy)} (derajat WGS84).
    Dua garis sekelompok bila kotak pembatasnya (diperlebar pad) jatuh pada sel grid yang sama. Grid berjangkar di
    koordinat absolut, sehingga kelompok hanya bergantung pada geometri garis itu sendiri, bukan pada luas wilayah
    yang diproses atau urutan berkas. Sel (~1,1 km) jauh lebih besar dari jangkauan interaksi (puluhan meter),
    jadi pengelompokan selalu konservatif: garis yang dapat berinteraksi pasti sekelompok.
    Hasil: daftar kelompok (daftar kunci terurut), urut menurut kunci terkecil."""
    parent = {}

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner = {}
    for k in sorted(boxes):
        parent[k] = k
        x0, y0, x1, y1 = boxes[k]
        for i in range(int(math.floor((x0 - pad_x) / cell)), int(math.floor((x1 + pad_x) / cell)) + 1):
            for j in range(int(math.floor((y0 - pad_y) / cell)), int(math.floor((y1 + pad_y) / cell)) + 1):
                o = owner.get((i, j))
                if o is None:
                    owner[(i, j)] = k
                else:
                    a, b = f(k), f(o)
                    if a != b:
                        parent[max(a, b)] = min(a, b)
    groups = {}
    for k in sorted(boxes):
        groups.setdefault(f(k), []).append(k)
    return [groups[r] for r in sorted(groups)]


def merge_results(parts):
    """Gabungkan hasil consolidate() dari beberapa kelompok ruang yang saling lepas menjadi satu hasil setara.
    Peringkat (rank) disusun ulang secara global menurut kunci prioritas; untai diurutkan dari yang terpanjang."""
    if len(parts) == 1:
        return parts[0]
    order, groups, params = [], {}, None
    for res in parts:
        order.extend(res["order"])
        params = params or res["params"]
        for g, d in res["groups"].items():
            m = groups.setdefault(g, {"chains": [], "comps": [], "gaps": [], "bridges": []})
            off = len(m["chains"])
            m["chains"].extend(d["chains"])
            m["comps"].extend([[c + off for c in comp] for comp in d["comps"]])
            m["gaps"].extend(d["gaps"])
            m["bridges"].extend(d["bridges"])
    order.sort(key=lambda r: r.key)
    for i, r in enumerate(order, 1):
        r.rank = i
    for m in groups.values():
        ch = m["chains"]
        m["comps"].sort(key=lambda comp: (-sum(line_len(ch[c][0]) for c in comp), min(_key(ch[c][0][0]) for c in comp)))
        m["gaps"].sort(key=lambda x: x[0])
    return {"order": order, "groups": {g: groups[g] for g in sorted(groups, key=lambda x: (x is None, str(x)))},
            "params": params}


# ------------------------------------------------------------------------------------------------ profil data
def separation_profile(records, max_d=10.0, bin_w=0.5, max_samples=150000):
    """Distribusi jarak setiap titik sampel garis ke garis LAIN terdekat (0..max_d m, per bin_w m), sebagai persen
    panjang. Dipakai untuk menilai apakah toleransi koridor cocok dengan data. Hasil dict: bins (persen per bin),
    cum (persen kumulatif), none (persen tanpa tetangga <= max_d), knee (Kneedle), step."""
    recs = [r for r in records if r.length > 0]
    total = sum(r.length for r in recs)
    if total <= 0:
        return None
    step = max(1.0, total / float(max_samples))
    idx = SegIndex(max(max_d * 2.0, 10.0))
    for r in recs:
        for k, p in enumerate(r.parts):
            idx.add_line(r.fid, k, p)
    nb = int(round(max_d / bin_w))
    bins = [0.0] * nb
    none = 0.0
    tot = 0.0
    for r in recs:
        for p in r.parts:
            cum, ms, smp = _sample(p, step)
            for i in range(len(ms) - 1):
                dl = ms[i + 1] - ms[i]
                tot += dl
                hit = idx.nearest(smp[i], max_d, skip=lambda o, li, f=r.fid: o == f)
                if hit is None:
                    none += dl
                else:
                    bins[min(nb - 1, int(hit[0] / bin_w))] += dl
    bins = [100.0 * b / tot for b in bins]
    cum, acc = [], 0.0
    for b in bins:
        acc += b
        cum.append(acc)
    return {"bins": bins, "cum": cum, "none": 100.0 * none / tot, "bin_w": bin_w, "max_d": max_d,
            "knee": kneedle(cum, bin_w), "step": step}


def kneedle(cum, bin_w):
    """Titik lutut kurva kumulatif cekung naik (Satopaa dkk. 2011, 'Kneedle'): titik dengan selisih terbesar
    antara kurva ternormalisasi dan garis diagonal."""
    if not cum or cum[-1] <= 0:
        return None
    n = len(cum)
    xs = [bin_w * (i + 1) for i in range(n)]
    best, bx = -1.0, None
    for x, y in zip(xs, cum):
        v = y / cum[-1] - x / xs[-1]
        if v > best:
            best, bx = v, x
    return bx


def cum_at(profile, d):
    """Persen panjang garis yang punya garis lain dalam jarak <= d (interpolasi linear)."""
    if not profile:
        return None
    w = profile["bin_w"]
    k = d / w
    i = int(k)
    if i <= 0:
        return profile["cum"][0] * k
    if i >= len(profile["cum"]):
        return profile["cum"][-1]
    return profile["cum"][i - 1] + (profile["cum"][i] - profile["cum"][i - 1]) * (k - i)
