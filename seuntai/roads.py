# -*- coding: utf-8 -*-
"""
Seuntai - data jalan OpenStreetMap otomatis untuk mode "cocokkan ke jalan".

Pengguna tidak memasukkan wilayah: Seuntai membaca lokasi data kabel lalu
  * area kecil (<= MAX_TILES petak 0,05 derajat): mengunduh jalan per petak lewat Overpass API;
  * area besar: mengunduh ekstrak wilayah Geofabrik (mis. Jawa, Sumatra, ...) sekali, lalu mengubahnya menjadi
    GeoPackage berisi jalan saja.
Hasil disimpan di cache profil QGIS dan dipakai ulang (diperbarui setelah REFRESH_DAYS hari bila ada internet).
Tanpa internet dan tanpa cache, mode jalan dilewati (koridor tetap tetap berjalan).

Data jalan (c) OpenStreetMap contributors, Open Database License (ODbL) - https://www.openstreetmap.org/copyright.
Seuntai hanya memakai jalan sebagai acuan keputusan; geometri/atribut OSM tidak ditulis ke hasil.

Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-2.0-or-later (see LICENSE).
"""
import gzip
import json
import math
import os
import time
import urllib.parse
import urllib.request

try:
    from . import core as C
except ImportError:  # uji di luar paket
    import core as C

UA = "Seuntai-QGIS-plugin/2.0 (+https://github.com/jetstimo/seuntai)"
TILE = 0.05                 # derajat (~5,5 km)
MAX_TILES = 8               # di atas ini memakai ekstrak Geofabrik. Uji laptop: 1 petak kota padat Overpass
                            # 30-50 s; ekstrak Jawa 899 MB 264 s + konversi 104 s, sesudahnya seluruh Jawa instan.
REFRESH_DAYS = 90
HIGHWAYS = tuple(sorted(C.ROAD_TOL))
OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter")
GEOFABRIK = "https://download.geofabrik.de/asia/indonesia/%s"
# Wilayah ekstrak Geofabrik untuk Indonesia; batas tepatnya dari berkas .poly yang diunduh.
REGIONS = ("java", "sumatra", "kalimantan", "sulawesi", "nusa-tenggara", "maluku", "papua")
ATTRIBUTION = "Data jalan © OpenStreetMap contributors (ODbL)"


class RoadError(Exception):
    pass


def _setting(key, default=""):
    try:
        from qgis.core import QgsSettings
        return QgsSettings().value("seuntai/" + key, default) or default
    except Exception:
        return os.environ.get("SEUNTAI_" + key.upper(), default)


def cache_dir():
    """Folder cache data jalan. Bisa dipindah (mis. ke drive D:) lewat QgsSettings 'seuntai/road_cache_dir'."""
    d = _setting("road_cache_dir")
    if not d:
        try:
            from qgis.core import QgsApplication
            base = QgsApplication.qgisSettingsDirPath()
        except Exception:
            base = os.path.join(os.path.expanduser("~"), ".seuntai")
        d = os.path.join(base, "seuntai_cache", "osm")
    os.makedirs(d, exist_ok=True)
    return d


def _fresh(path, days=REFRESH_DAYS):
    return os.path.exists(path) and (time.time() - os.path.getmtime(path)) < days * 86400


def _get(url, data=None, timeout=180):
    """GET/POST kecil. Di QGIS memakai jaringan QGIS (proxy dan sertifikat sesuai pengaturan QGIS).
    Dari thread Python biasa (unduhan paralel) selalu urllib: QgsBlockingNetworkRequest di thread seperti itu bisa
    menunggu thread utama yang sedang sibuk sampai batas waktu habis (uji QGIS 3.40: 200 s)."""
    import threading
    th = threading.current_thread()
    if th is not threading.main_thread() and not isinstance(th, threading._DummyThread):
        return _get_urllib(url, data, timeout)
    try:
        from qgis.core import QgsBlockingNetworkRequest
        from qgis.PyQt.QtCore import QByteArray, QUrl
        from qgis.PyQt.QtNetwork import QNetworkRequest
    except ImportError:
        QgsBlockingNetworkRequest = None
    if QgsBlockingNetworkRequest is not None:
        nr = QNetworkRequest(QUrl(url))
        nr.setRawHeader(b"User-Agent", UA.encode())
        if hasattr(nr, "setTransferTimeout"):
            nr.setTransferTimeout(int(timeout * 1000))
        br = QgsBlockingNetworkRequest()
        if data is not None:
            nr.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader if hasattr(QNetworkRequest, "KnownHeaders")
                         else QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
            err = br.post(nr, QByteArray(data))
        else:
            err = br.get(nr)
        ok = getattr(QgsBlockingNetworkRequest, "NoError", None)
        if ok is None:
            ok = QgsBlockingNetworkRequest.ErrorCode.NoError
        if err == ok:
            return bytes(br.reply().content())
        qerr = br.errorMessage() or "network error"
        # gagal lewat jaringan QGIS (mis. di thread pekerja): coba sekali lagi lewat urllib + proxy QGIS
        try:
            return _get_urllib(url, data, timeout)
        except Exception as e:
            raise RoadError("%s; %s" % (qerr, e))
    return _get_urllib(url, data, timeout)


def _https(url):
    """Hanya alamat https:// yang boleh diunduh (tidak ada file:// atau skema lain lewat urllib)."""
    if not str(url).lower().startswith("https://"):
        raise RoadError("only https:// addresses are allowed: %s" % url)
    return url


def _get_urllib(url, data, timeout):
    req = urllib.request.Request(_https(url), data=data, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})  # nosec B310
    with _opener().open(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw


def _opener():
    """urllib dengan proxy dari pengaturan QGIS (Settings > Options > Network), bila diaktifkan."""
    handlers = []
    try:
        from qgis.core import QgsSettings
        s = QgsSettings()
        if str(s.value("proxy/proxyEnabled", "false")).lower() == "true":
            host = s.value("proxy/proxyHost", "")
            port = s.value("proxy/proxyPort", "")
            user = s.value("proxy/proxyUser", "")
            pwd = s.value("proxy/proxyPassword", "")
            if host:
                auth = ("%s:%s@" % (urllib.parse.quote(user), urllib.parse.quote(pwd))) if user else ""
                px = "http://%s%s%s" % (auth, host, (":%s" % port) if port else "")
                handlers.append(urllib.request.ProxyHandler({"http": px, "https": px}))
    except Exception:
        pass
    return urllib.request.build_opener(*handlers)


def _download(url, path, feedback=None, label=""):
    """Unduh berkas besar bertahap ke disk (tidak menampung seluruh isi di memori)."""
    req = urllib.request.Request(_https(url), headers={"User-Agent": UA})  # nosec B310 - https saja (_https)
    tmp = path + ".part"
    t0 = time.time()
    with _opener().open(req, timeout=120) as r, open(tmp, "wb") as f:
        tot = int(r.headers.get("Content-Length") or 0)
        got = 0
        last = 0
        while True:
            if feedback is not None and feedback.isCanceled():
                raise RoadError("canceled")
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            got += len(b)
            if feedback is not None and got - last >= 8 << 20:
                last = got
                feedback.setProgressText("Downloading road data for %s (one time): %.0f of %.0f MB..."
                                         % (label.title(), got / 1e6, tot / 1e6))
                feedback.pushInfo("  %s: %.0f / %.0f MB (%.1f MB/s)" % (label, got / 1e6, tot / 1e6,
                                                                      got / 1e6 / max(time.time() - t0, 0.1)))
    os.replace(tmp, path)


# ------------------------------------------------------------------------------------------------ wilayah
def _parse_poly(text):
    rings, cur = [], None
    for ln in text.splitlines()[1:]:
        s = ln.strip()
        if not s:
            continue
        if s == "END":
            if cur is not None:
                rings.append(cur)
                cur = None
            continue
        if cur is None:
            cur = [] if not s.startswith("!") else None
            if cur is None:
                cur = "hole"
            continue
        if cur == "hole":
            continue
        xy = s.split()
        cur.append((float(xy[0]), float(xy[1])))
    return [r for r in rings if isinstance(r, list) and len(r) >= 3]


def _in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-300) + xi:
            inside = not inside
        j = i
    return inside


def region_polys(feedback=None):
    d = cache_dir()
    out = {}
    for rg in REGIONS:
        p = os.path.join(d, rg + ".poly")
        if not os.path.exists(p):
            try:
                open(p, "wb").write(_get(GEOFABRIK % (rg + ".poly"), timeout=60))
            except Exception as e:
                if feedback is not None:
                    feedback.pushInfo("Region outline %s not available: %s" % (rg, e))
                continue
        out[rg] = _parse_poly(open(p, encoding="utf-8").read())
    return out


def regions_for(points, feedback=None):
    """Wilayah Geofabrik yang memuat titik-titik data (lon, lat). Titik di luar Indonesia -> None."""
    polys = region_polys(feedback)
    need, outside = set(), 0
    for x, y in points:
        hit = None
        for rg, rings in polys.items():
            if any(_in_ring(x, y, r) for r in rings):
                hit = rg
                break
        if hit:
            need.add(hit)
        else:
            outside += 1
    return need, outside


def ensure_region(rg, feedback=None):
    """GeoPackage jalan untuk satu wilayah (unduh ekstrak .osm.pbf + konversi bila belum ada / sudah lama)."""
    d = cache_dir()
    gpkg = os.path.join(d, "%s_roads.gpkg" % rg)
    if _fresh(gpkg):
        return gpkg
    pbf = os.path.join(d, "%s-latest.osm.pbf" % rg)
    try:
        import shutil
        free = shutil.disk_usage(d).free
        if free < 3.0e9 and not os.path.exists(gpkg):
            raise RoadError("not enough free disk space for the '%s' road data (%.1f GB free, about 3 GB needed). "
                            "Free some space or set another cache folder" % (rg, free / 1e9))
    except (OSError, ImportError):
        pass
    try:
        if feedback is not None:
            feedback.pushInfo("Downloading OpenStreetMap roads for '%s' (one time, then cached)..." % rg)
        _download(GEOFABRIK % ("%s-latest.osm.pbf" % rg), pbf, feedback, rg)
    except RoadError:
        raise
    except Exception as e:
        if os.path.exists(gpkg):
            if feedback is not None:
                feedback.pushWarning("Road data for '%s' could not be refreshed (%s); using the cached copy." % (rg, e))
            return gpkg
        raise RoadError("download failed: %s" % e)
    from osgeo import gdal
    if feedback is not None:
        feedback.pushInfo("Extracting roads from the OpenStreetMap file (a few minutes)...")
        feedback.setProgressText("Extracting roads for %s (one time, about 2 minutes)..." % rg.title())
    gdal.SetConfigOption("OSM_USE_CUSTOM_INDEXING", "YES")
    gdal.SetConfigOption("OSM_MAX_TMPFILE_SIZE", "1024")
    tmp = gpkg + ".tmp.gpkg"
    if os.path.exists(tmp):
        os.remove(tmp)
    where = "highway IN (%s)" % ",".join("'%s'" % h for h in HIGHWAYS)
    opts = gdal.VectorTranslateOptions(format="GPKG", layers=["lines"], where=where, layerName="roads",
                                       selectFields=["osm_id", "highway", "name", "other_tags"])
    ds = gdal.VectorTranslate(tmp, pbf, options=opts)
    if ds is None:
        raise RoadError("could not read the OpenStreetMap file")
    ds = None
    os.replace(tmp, gpkg)
    try:
        os.remove(pbf)
    except OSError:
        pass
    return gpkg


def _oneway(other_tags):
    s = other_tags or ""
    return '"oneway"=>"yes"' in s or '"oneway"=>"1"' in s or '"oneway"=>"-1"' in s


def _label(name, fid):
    nm = (name or "").strip().lower()
    return ("n:" + nm) if nm else ("w:%s" % fid)


# ------------------------------------------------------------------------------------------------ petak Overpass
def tiles_for(boxes):
    out = set()
    for b in boxes:
        for tx in range(int(math.floor(b[0] / TILE)), int(math.floor(b[2] / TILE)) + 1):
            for ty in range(int(math.floor(b[1] / TILE)), int(math.floor(b[3] / TILE)) + 1):
                out.add((tx, ty))
    return sorted(out)


def tile_roads(tx, ty, feedback=None):
    """Jalan satu petak dari cache atau Overpass -> [(pts_lonlat, highway, label, oneway)]."""
    d = os.path.join(cache_dir(), "tiles")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "v2_%d_%d.json.gz" % (tx, ty))
    js = None
    if _fresh(p):
        js = json.loads(gzip.open(p, "rb").read().decode("utf-8"))
    else:
        s, w = ty * TILE, tx * TILE
        q = '[out:json][timeout:180];way["highway"~"^(%s)$"](%.5f,%.5f,%.5f,%.5f);out tags geom;' % (
            "|".join(HIGHWAYS), s, w, s + TILE, w + TILE)
        err = None
        for attempt, ep in enumerate(OVERPASS + OVERPASS[:1]):
            try:
                if attempt:
                    time.sleep(5.0 * attempt)       # beri jeda sebelum mencoba lagi (pemakaian wajar Overpass)
                raw = _get(ep, ("data=" + urllib.parse.quote(q)).encode(), timeout=200)
                js = json.loads(raw.decode("utf-8"))
                rem = str(js.get("remark") or "")
                # Overpass mengembalikan 'elements: []' + remark saat waktu habis / sibuk: itu GAGAL, bukan petak kosong
                if "elements" not in js or (not js["elements"] and rem):
                    raise RoadError("Overpass: %s" % (rem[:120] or "no elements"))
                gzip.open(p, "wb").write(json.dumps(js, separators=(",", ":")).encode("utf-8"))
                break
            except Exception as e:      # coba server cermin berikutnya
                err = e
                js = None
        if js is None:
            if os.path.exists(p):
                js = json.loads(gzip.open(p, "rb").read().decode("utf-8"))
            else:
                raise RoadError("Overpass failed: %s" % err)
    out = []
    for el in js.get("elements", []):
        t = el.get("tags", {})
        g = el.get("geometry") or []
        if len(g) < 2 or t.get("highway") not in C.ROAD_TOL:
            continue
        out.append(([(n["lon"], n["lat"]) for n in g], t.get("highway"), _label(t.get("name"), el.get("id")),
                    t.get("oneway") in ("yes", "1", "-1")))
    return out


# ------------------------------------------------------------------------------------------------ paket petak jalan
# Paket petak: jalan OSM yang sudah dipotong per petak PACK_TILE derajat dan dipadatkan (koordinat bilangan bulat
# 1e-7 derajat = presisi asli OSM, selisih berurutan). Satu kota (mis. Bandung) = beberapa MB, unduh dalam detik,
# tanpa membebani server Overpass. Server paket diatur di PACK_URL / QgsSettings 'seuntai/road_pack_url'
# (alamat web atau folder lokal). Isi: index.json + <tx>_<ty>.json.gz. Dibuat dengan tools/build_road_pack.py.
PACK_TILE = 0.1
PACK_URL = "https://jetstimo.github.io/seuntai/pack"     # dibangun ulang tiap bulan oleh GitHub Actions
HW_CODES = HIGHWAYS


def pack_encode(ways):
    """ways: [(osm_id, highway, name, oneway, [(lon, lat), ...])] -> bytes gzip."""
    names, nid, out = [], {}, []
    for wid, hw, nm, ow, pts in ways:
        if hw not in HW_CODES or len(pts) < 2:
            continue
        ni = -1
        if nm:
            ni = nid.get(nm)
            if ni is None:
                ni = nid[nm] = len(names)
                names.append(nm)
        xy, px, py = [], 0, 0
        for x, y in pts:
            ix, iy = int(round(x * 1e7)), int(round(y * 1e7))
            xy.append(ix - px)
            xy.append(iy - py)
            px, py = ix, iy
        out.append([int(wid), HW_CODES.index(hw), ni, 1 if ow else 0, xy])
    raw = json.dumps({"v": 1, "hw": list(HW_CODES), "n": names, "w": out}, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return gzip.compress(raw, 9)


def pack_decode(blob):
    js = json.loads(gzip.decompress(blob).decode("utf-8"))
    hw, names, out = js["hw"], js["n"], []
    for wid, h, ni, ow, xy in js["w"]:
        pts, x, y = [], 0, 0
        for k in range(0, len(xy), 2):
            x += xy[k]
            y += xy[k + 1]
            pts.append((x * 1e-7, y * 1e-7))
        nm = names[ni] if ni >= 0 else None
        out.append((pts, hw[h], _label(nm, wid), bool(ow), wid))
    return out


def pack_tiles_for(boxes):
    out = set()
    for b in boxes:
        for tx in range(int(math.floor(b[0] / PACK_TILE)), int(math.floor(b[2] / PACK_TILE)) + 1):
            for ty in range(int(math.floor(b[1] / PACK_TILE)), int(math.floor(b[3] / PACK_TILE)) + 1):
                out.add((tx, ty))
    return sorted(out)


def _pack_get(base, name, timeout=60):
    if not base:
        raise RoadError("no road pack server configured")
    if "://" not in base or base.startswith("file://"):
        p = os.path.join(base[7:] if base.startswith("file://") else base, name)
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        return open(p, "rb").read()
    return _get(base.rstrip("/") + "/" + name, timeout=timeout)


class RoadPack:
    """Klien paket petak jalan dengan cache lokal (dipakai ulang REFRESH_DAYS hari)."""

    def __init__(self, base, feedback=None):
        self.base = base
        self.feedback = feedback
        self.dir = os.path.join(cache_dir(), "pack")
        os.makedirs(self.dir, exist_ok=True)
        ip = os.path.join(self.dir, "index.json")
        idx = None
        if _fresh(ip, 7):
            idx = json.loads(open(ip, encoding="utf-8").read())
        else:
            try:
                idx = json.loads(_pack_get(base, "index.json", 30).decode("utf-8"))
                open(ip, "w", encoding="utf-8").write(json.dumps(idx))
            except Exception as e:
                if os.path.exists(ip):
                    idx = json.loads(open(ip, encoding="utf-8").read())
                else:
                    raise RoadError("road pack index not available: %s" % e)
        self.index = idx
        self.tiles = set(idx.get("tiles", {}))
        self.built = idx.get("built", "")

    def covers(self, boxes):
        """True bila semua titik data berada di wilayah paket (petak di luar daratan memang tidak ada)."""
        ext = self.index.get("extent")
        if not ext:
            return False
        return all(ext[0] <= (b[0] + b[2]) / 2.0 <= ext[2] and ext[1] <= (b[1] + b[3]) / 2.0 <= ext[3]
                   for b in boxes)

    def load(self, keys):
        """{(tx, ty): [ways]} untuk petak yang diminta; unduh yang belum ada di cache (4 sekaligus)."""
        res, todo = {}, []
        for t in keys:
            name = "%d_%d.json.gz" % t
            if name[:-8] not in self.tiles:
                res[t] = []
                continue
            p = os.path.join(self.dir, name)
            if _fresh(p) and os.path.getsize(p) == self.index["tiles"][name[:-8]]:
                res[t] = pack_decode(open(p, "rb").read())
            else:
                todo.append((t, name, p))
        if todo:
            from concurrent.futures import ThreadPoolExecutor
            done = [0]

            def fetch(item):
                t, name, p = item
                blob, err = None, None
                for attempt in range(3):
                    try:
                        blob = _pack_get(self.base, name)
                        if len(blob) != self.index["tiles"][name[:-8]]:
                            raise RoadError("incomplete download")
                        break
                    except Exception as e:
                        err, blob = e, None
                        time.sleep(1.0 + attempt)
                done[0] += 1
                if self.feedback is not None:
                    self.feedback.setProgressText("Downloading road data: %d of %d areas..." % (done[0], len(todo)))
                if blob is None:
                    return t, None, err
                with open(p + ".part", "wb") as f:
                    f.write(blob)
                os.replace(p + ".part", p)
                return t, blob, None
            with ThreadPoolExecutor(max_workers=4) as ex:
                for t, blob, err in ex.map(fetch, todo):
                    if blob is None:
                        p = os.path.join(self.dir, "%d_%d.json.gz" % t)
                        if os.path.exists(p):          # salinan lama lebih baik daripada tidak ada
                            res[t] = pack_decode(open(p, "rb").read())
                        else:
                            raise RoadError("road data could not be downloaded (%s)" % err)
                    else:
                        res[t] = pack_decode(blob)
        return res


# ------------------------------------------------------------------------------------------------ pemuat utama
def cached_regions():
    """Wilayah yang GeoPackage jalannya sudah ada di cache (berapa pun umurnya)."""
    d = cache_dir()
    return [rg for rg in REGIONS if os.path.exists(os.path.join(d, "%s_roads.gpkg" % rg))]


class RoadSource:
    """Menyediakan jalan (lon, lat) untuk kotak-kotak data. Dibuat sekali per proses."""

    def __init__(self, boxes, feedback=None):
        self.feedback = feedback
        self.mode = None
        self.gpkgs = []
        self.tiles = {}
        self.note = ""
        boxes = list(boxes)
        tiles = tiles_for(boxes)
        self.n_tiles = len(tiles)
        pts = [((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0) for b in boxes[:: max(1, len(boxes) // 4000)]]
        have = cached_regions()
        if have:      # wilayah sudah pernah diunduh -> langsung dipakai, berapa pun luas data
            polys = {rg: p for rg, p in region_polys(feedback).items() if rg in have}
            hit = set()
            ok = bool(polys)
            for x, y in pts:
                rg = next((r for r, rings in polys.items() if any(_in_ring(x, y, ri) for ri in rings)), None)
                if rg is None:
                    ok = False
                    break
                hit.add(rg)
            if ok:
                for rg in sorted(hit):
                    self.gpkgs.append(ensure_region(rg, feedback))
                self.mode = "geofabrik:" + ",".join(sorted(hit))
                return
        base = _setting("road_pack_url", PACK_URL)
        if base:      # paket petak: unduhan kecil per kota, cepat dan ringan
            try:
                pk = RoadPack(base, feedback)
                if pk.covers(boxes):
                    self.pack = pk
                    self.mode = "pack:" + (pk.built or "?")
                    return
            except RoadError as e:
                self.note = str(e)
        if len(tiles) <= MAX_TILES:
            self.mode = "overpass"
            return
        if str(_setting("allow_region_download", "false")).lower() != "true":
            # Ekstrak pulau ~0,1-1 GB: tidak diunduh diam-diam. Tanpa paket petak, area besar memakai koridor saja.
            raise RoadError("road data server not reachable (%s) and the area is too large for the OpenStreetMap "
                            "live service (%d areas)" % (self.note or "no road pack server", len(tiles)))
        need, outside = regions_for(pts, feedback)
        if not need:
            raise RoadError("data is outside the supported OpenStreetMap regions and too large for Overpass "
                            "(%d tiles)" % len(tiles))
        for rg in sorted(need):
            self.gpkgs.append(ensure_region(rg, feedback))
        self.mode = "geofabrik:" + ",".join(sorted(need))
        if outside:
            self.note = "%d sample points lie outside the downloaded regions" % outside

    def roads_in(self, boxes):
        """Jalan yang memotong salah satu kotak (lon0, lat0, lon1, lat1) -> [(pts_lonlat, hw, label, oneway)]."""
        if self.mode.startswith("pack"):
            got = self.pack.load(pack_tiles_for(boxes))
            out, seen = [], set()
            for t in sorted(got):
                for pts, hw, lab, ow, wid in got[t]:
                    if wid not in seen:
                        seen.add(wid)
                        out.append((pts, hw, lab, ow))
            return out
        if self.mode == "overpass":
            need = sorted(set(tiles_for(boxes)))
            todo = [t for t in need if t not in self.tiles]
            if todo:
                # 2 permintaan sekaligus = batas slot Overpass per alamat IP (pemakaian wajar); ~2x lebih cepat
                from concurrent.futures import ThreadPoolExecutor
                done = [0]

                def fetch(t):
                    if self.feedback is not None and self.feedback.isCanceled():
                        return t, [], None
                    try:
                        r = tile_roads(t[0], t[1])
                        e = None
                    except RoadError as ex:      # satu petak gagal: lanjut, catat
                        r, e = [], ex
                    done[0] += 1
                    if self.feedback is not None:
                        self.feedback.setProgressText("Downloading OpenStreetMap roads: %d of %d areas (one time, "
                                                      "then cached)..." % (done[0], len(todo)))
                    return t, r, e
                if self.feedback is not None:
                    self.feedback.setProgressText("Downloading OpenStreetMap roads: 0 of %d areas (one time, then "
                                                  "cached)..." % len(todo))
                with ThreadPoolExecutor(max_workers=2) as ex:
                    for t, r, e in ex.map(fetch, todo):
                        self.tiles[t] = r
                        if e is not None:
                            self.failed = getattr(self, "failed", 0) + 1
                            self.note = "%d OpenStreetMap areas could not be downloaded (%s)" % (self.failed, e)
            out, seen = [], set()
            for (tx, ty) in need:
                for r in self.tiles[(tx, ty)]:
                    key = (r[2], r[0][0], r[0][-1])
                    if key not in seen:
                        seen.add(key)
                        out.append(r)
            return out
        return self._iter_gpkg(tiles_for(boxes))

    def _iter_gpkg(self, grid):
        from osgeo import ogr
        seen = set()
        for gp in self.gpkgs:
            ds = ogr.Open(gp)
            if ds is None:
                continue
            lyr = ds.GetLayerByName("roads") or ds.GetLayer(0)
            for (tx, ty) in grid:
                if self.feedback is not None and self.feedback.isCanceled():
                    break
                lyr.SetSpatialFilterRect(tx * TILE, ty * TILE, (tx + 1) * TILE, (ty + 1) * TILE)
                for f in lyr:
                    fid = f.GetFID()
                    if (gp, fid) in seen:
                        continue
                    seen.add((gp, fid))
                    hw = f.GetField("highway")
                    if hw not in C.ROAD_TOL:
                        continue
                    g = f.GetGeometryRef()
                    if g is None:
                        continue
                    pts = g.GetPoints() or []
                    if len(pts) < 2:
                        continue
                    yield ([(p[0], p[1]) for p in pts], hw, _label(f.GetField("name"), fid),
                           _oneway(f.GetField("other_tags")))
            lyr.SetSpatialFilter(None)
            ds = None
