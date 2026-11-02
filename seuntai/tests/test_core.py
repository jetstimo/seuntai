# -*- coding: utf-8 -*-
"""Uji otomatis inti Seuntai (Python murni, tanpa QGIS). Jalankan: python seuntai/tests/test_core.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from seuntai import core as C          # noqa: E402
from seuntai import roads as R         # noqa: E402


def run(lines, roads=None, tol=7.5):
    recs = [C.Record(i, [pts], None) for i, pts in enumerate(lines)]
    rm = C.RoadMatcher(roads) if roads is not None else None
    res = C.consolidate(recs, tol=tol, min_cover=0.8, smart_tol=10.0, roads=rm)
    return {r.fid: r.status for r in res["order"]}, res


def kept(st):
    return sorted(k for k, v in st.items() if v in (C.DIPAKAI, C.DIPANGKAS))


def line(y, x0=0.0, x1=500.0, n=26):
    return [(x0 + (x1 - x0) * i / (n - 1), y) for i in range(n)]


ROAD = [(line(0.0), "residential", "n:jalan uji", False)]


def test_identical_and_near_lines_become_one():
    st, _ = run([line(0.0), line(0.0), line(4.0)])
    assert kept(st) == [0], st


def test_two_sides_of_road_need_road_matching():
    # kabel 10 m di kiri dan kanan jalan (20 m terpisah, di atas koridor 15 m)
    st, _ = run([line(10.0), line(-10.0)])
    assert kept(st) == [0, 1], st                       # koridor saja: dua garis
    st, _ = run([line(10.0), line(-10.0)], ROAD)
    assert len(kept(st)) == 1, st                       # cocok ke jalan: satu garis


def test_parallel_alley_is_not_merged():
    # gang sejajar 30 m dari jalan utama adalah jalan lain -> tetap dua garis
    roads = ROAD + [(line(30.0), "service", "n:gang lain", False)]
    st, _ = run([line(3.0), line(29.0)], roads)
    assert kept(st) == [0, 1], st


def test_road_order_does_not_change_result():
    roads = ROAD + [(line(30.0), "service", "n:gang lain", False), ([(250.0, -200.0), (250.0, 200.0)], "tertiary", None, False)]
    lines = [line(10.0), line(-10.0), line(29.0), [(255.0, -150.0), (255.0, 150.0)]]
    a, _ = run(lines, roads)
    b, _ = run(lines, roads[::-1])
    assert a == b, (a, b)


def test_pack_roundtrip_is_lossless():
    ways = [(1, "primary", "Jalan A", True, [(107.6123456, -6.9412345), (107.62, -6.93)]),
            (2, "residential", None, False, [(107.61, -6.94), (107.611, -6.941)])]
    out = R.pack_decode(R.pack_encode(ways))
    assert [o[1:] for o in out] == [("primary", "n:jalan a", True, 1), ("residential", "w:2", False, 2)]
    assert max(abs(a - b) for (p, *_), w in zip(out, ways) for (a, _), (b, _) in zip(p, w[4])) < 1e-9


def test_dates_rank_oldest_first():
    import datetime
    recs = [C.Record(0, [line(0.0)], datetime.datetime(2023, 1, 1)), C.Record(1, [line(2.0)], datetime.datetime(2019, 1, 1))]
    res = C.consolidate(recs, tol=7.5, min_cover=0.8, smart_tol=10.0)
    st = {r.fid: r.status for r in res["order"]}
    assert kept(st) == [1], st


if __name__ == "__main__":
    n = 0
    for k, f in sorted(globals().items()):
        if k.startswith("test_"):
            f()
            n += 1
            print("ok", k)
    print("%d uji lulus" % n)
