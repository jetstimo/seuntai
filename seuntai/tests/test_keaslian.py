"""Uji keaslian rilis Seuntai (murni Python): sidik kunci, cek silang, ganti kunci, verifikasi online.
Jalankan: python seuntai/tests/test_keaslian.py"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import keaslian as K   # noqa: E402


def _copy_mirrors(d, old=None, new=None):
    for f in K.CERMIN:
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            t = fh.read()
        with open(os.path.join(d, f), "w", encoding="utf-8") as fh:
            fh.write(t.replace(old, new) if old else t)


class Keaslian(unittest.TestCase):
    def test_rfc8032(self):
        sk = bytes(range(32))
        sig = K.sign(sk, b"seuntai")
        self.assertTrue(K.verify(K.public_key(sk), b"seuntai", sig))
        self.assertFalse(K.verify(K.public_key(sk), b"seuntai!", sig))

    def test_sidik_resmi(self):
        self.assertEqual(K.sidik(K.from_ints(K.KUNCI_PUBLIK)), K.SIDIK_RESMI)
        self.assertEqual(K.cermin_beda(ROOT), [])

    def test_siklus_dan_serangan(self):
        d = tempfile.mkdtemp()
        old, old_fp = K.KUNCI_PUBLIK, K.SIDIK_RESMI
        try:
            sk = os.urandom(32)
            fp = K.sidik(K.public_key(sk))
            _copy_mirrors(d, old_fp, fp)
            open(os.path.join(d, "a.py"), "w").write("x = 1\n")
            K.KUNCI_PUBLIK, K.SIDIK_RESMI = tuple(K.to_ints(K.public_key(sk))), fp
            man = K.write_signed(d, "9.9.9", sk)
            K._CACHE.clear()
            self.assertEqual(K.check(d)[0], "ASLI")
            reg = {"kunci_sidik": fp, "rilis": {"9.9.9": {"manifest": K.sidik_manifest(man)}}}
            self.assertEqual(K.verify_online(lambda u: json.dumps(reg).encode(), root=d)[0], "TERVERIFIKASI")
            open(os.path.join(d, "a.py"), "w").write("x = 2\n")
            K._CACHE.clear()
            self.assertEqual(K.check(d)[0], "DIMODIFIKASI")
            K.KUNCI_PUBLIK = tuple(K.to_ints(K.public_key(os.urandom(32))))      # kunci penyerang
            K._CACHE.clear()
            self.assertEqual(K.check(d)[0], "TIDAK_RESMI")
        finally:
            K.KUNCI_PUBLIK, K.SIDIK_RESMI = old, old_fp
            K._CACHE.clear()
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
