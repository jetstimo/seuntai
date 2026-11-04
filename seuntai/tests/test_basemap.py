"""Uji peta dasar Seuntai (murni Python): ubin, tilemap Esri, nilai aman.
Jalankan: python seuntai/tests/test_basemap.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import basemap as B   # noqa: E402


class PetaDasar(unittest.TestCase):
    def test_ubin(self):
        self.assertEqual(B.tile_xy(124.8355, 1.3395, 19), (443948, 260193))
        self.assertTrue(B.tilemap_url(124.8355, 1.3395, 18).endswith("/tilemap/18/130095/221973/3/3"))

    def test_tilemap(self):
        self.assertTrue(B.parse_tilemap('{"data":[1,1,1,1,1,1,1,1,1],"valid":true}'))
        self.assertFalse(B.parse_tilemap('{"data":[0,0,0,0,0,0,0,0,0],"valid":true}'))
        self.assertFalse(B.parse_tilemap("x"))

    def test_bersama_seranta(self):
        self.assertIn("seranta_basemap", B.PROPS)
        self.assertEqual(B.ZMAX_DEFAULT["sat"], 17)


if __name__ == "__main__":
    unittest.main()
