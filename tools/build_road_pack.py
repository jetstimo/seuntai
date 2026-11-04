# -*- coding: utf-8 -*-
"""
Seuntai - pembuat paket petak jalan (road pack) dari data OpenStreetMap.

Masukan : GeoPackage jalan hasil konversi ekstrak Geofabrik (layer 'roads', kolom osm_id, highway, name, other_tags),
          atau berkas .osm.pbf (dikonversi dulu dengan GDAL).
Keluaran: <out>/index.json + <out>/<tx>_<ty>.json.gz (petak 0,1 derajat). Lihat roads.pack_encode untuk formatnya.

Contoh (Python QGIS / OSGeo4W, atau CI dengan python3-gdal):
    python build_road_pack.py out_folder java_roads.gpkg sumatra_roads.gpkg ...

Data (c) OpenStreetMap contributors, ODbL 1.0. Paket ini adalah basis data turunan dan wajib dibagikan dengan lisensi
ODbL beserta atribusi. Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-3.0-or-later.
"""
import datetime
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "seuntai"))
sys.path.insert(0, os.path.join(HERE, ".."))
try:
    from seuntai import roads as R
except ImportError:
    import roads as R
from osgeo import gdal, ogr

BLOCK = 1.0     # derajat; data dibaca per blok agar memori kecil


def pbf_to_gpkg(pbf, gpkg):
    gdal.SetConfigOption("OSM_USE_CUSTOM_INDEXING", "YES")
    gdal.SetConfigOption("OSM_MAX_TMPFILE_SIZE", "1024")
    where = "highway IN (%s)" % ",".join("'%s'" % h for h in R.HIGHWAYS)
    opts = gdal.VectorTranslateOptions(format="GPKG", layers=["lines"], where=where, layerName="roads",
                                       selectFields=["osm_id", "highway", "name", "other_tags"])
    ds = gdal.VectorTranslate(gpkg, pbf, options=opts)
    ds = None
    return gpkg


def build(out, sources, log=print, drop_pbf=False):
    os.makedirs(out, exist_ok=True)
    T = R.PACK_TILE
    index, ext, nways = {}, [180.0, 90.0, -180.0, -90.0], 0
    t0 = time.time()
    for src in sources:
        if src.lower().endswith(".pbf"):
            pbf = src
            src = pbf_to_gpkg(pbf, os.path.splitext(pbf)[0] + "_roads.gpkg")
            log("konversi %s selesai, %.0f s" % (os.path.basename(pbf), time.time() - t0))
            if drop_pbf:
                os.remove(pbf)          # hemat disk (runner CI)
        ds = ogr.Open(src)
        lyr = ds.GetLayerByName("roads") or ds.GetLayer(0)
        x0, x1, y0, y1 = lyr.GetExtent()
        ext = [min(ext[0], x0), min(ext[1], y0), max(ext[2], x1), max(ext[3], y1)]
        bx0, by0 = int(math.floor(x0 / BLOCK)), int(math.floor(y0 / BLOCK))
        bx1, by1 = int(math.floor(x1 / BLOCK)), int(math.floor(y1 / BLOCK))
        per = int(round(BLOCK / T))
        for bx in range(bx0, bx1 + 1):
            for by in range(by0, by1 + 1):
                lyr.SetSpatialFilterRect(bx * BLOCK, by * BLOCK, (bx + 1) * BLOCK, (by + 1) * BLOCK)
                tiles = {}
                for f in lyr:
                    hw = f.GetField("highway")
                    if hw not in R.HW_CODES:
                        continue
                    g = f.GetGeometryRef()
                    if g is None:
                        continue
                    pts = [(p[0], p[1]) for p in (g.GetPoints() or [])]
                    if len(pts) < 2:
                        continue
                    try:
                        wid = int(f.GetField("osm_id"))
                    except (TypeError, ValueError):
                        wid = -f.GetFID()
                    rec = (wid, hw, f.GetField("name"), R._oneway(f.GetField("other_tags")), pts)
                    keys = set()
                    for k in range(len(pts) - 1):
                        (ax, ay), (cx, cy) = pts[k], pts[k + 1]
                        for tx in range(int(math.floor(min(ax, cx) / T)), int(math.floor(max(ax, cx) / T)) + 1):
                            for ty in range(int(math.floor(min(ay, cy) / T)), int(math.floor(max(ay, cy) / T)) + 1):
                                if bx * per <= tx < (bx + 1) * per and by * per <= ty < (by + 1) * per:
                                    keys.add((tx, ty))
                    for key in keys:
                        tiles.setdefault(key, {})[wid] = rec
                for (tx, ty), ways in tiles.items():
                    name = "%d_%d" % (tx, ty)
                    p = os.path.join(out, name + ".json.gz")
                    if name in index:          # petak berbatasan dua sumber (mis. Jawa & Bali): gabung
                        old = {w[4]: w for w in R.pack_decode(open(p, "rb").read())}
                        for pts, hw, lab, ow, wid in old.values():
                            ways.setdefault(wid, (wid, hw, lab[2:] if lab.startswith("n:") else None, ow, pts))
                    blob = R.pack_encode(sorted(ways.values(), key=lambda w: w[0]))
                    open(p, "wb").write(blob)
                    index[name] = len(blob)
                    nways += len(ways)
                log("blok %d,%d: %d petak, total %d petak, %.0f s" % (bx, by, len(tiles), len(index), time.time() - t0))
        lyr.SetSpatialFilter(None)
        ds = None
        if drop_pbf and src.endswith("_roads.gpkg"):
            os.remove(src)
    meta = {"v": 1, "tile": T, "built": datetime.date.today().isoformat(), "extent": ext, "tiles": index,
            "attribution": "(c) OpenStreetMap contributors, ODbL 1.0 - https://www.openstreetmap.org/copyright",
            "sources": [os.path.basename(s) for s in sources]}
    open(os.path.join(out, "index.json"), "w", encoding="utf-8").write(json.dumps(meta, separators=(",", ":")))
    tot = sum(index.values())
    log("SELESAI: %d petak, %.1f MB, %d ruas-petak, %.0f s" % (len(index), tot / 1e6, nways, time.time() - t0))
    return meta


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--drop-pbf"]
    build(args[0], args[1:], drop_pbf="--drop-pbf" in sys.argv)
