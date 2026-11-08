# -*- coding: utf-8 -*-
"""Uji 2.3.0: kolom & nilai dikenali walau nama salah ketik / berbeda (Python murni)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deteksi as D  # noqa: E402


class T(unittest.TestCase):
    def test_date_typo_and_compound(self):
        s = {"CRETEDATE": ["2020-01-02", "2021-05-01"]}
        self.assertEqual(D.pick_date_field([("ID", "int"), ("CRETEDATE", "str")], s)[0], "CRETEDATE")
        s = {"CREATE_DT": ["2020-01-02", "2021-05-01"], "EDIT_DT": ["2022-01-01", "2022-02-01"]}
        self.assertEqual(D.pick_date_field([("EDIT_DT", "str"), ("CREATE_DT", "str")], s)[0], "CREATE_DT")
        # kolom ubah/hapus tidak pernah dipilih
        s = {"LASTEDITDATE": ["2020-01-02"]}
        self.assertIsNone(D.pick_date_field([("LASTEDITDATE", "str")], s)[0])

    def test_product(self):
        self.assertEqual(D.pick_product_field(["NAME", "PRODCUT"]), "PRODCUT")
        self.assertEqual(D.pick_product_field(["NAME", "LOB_TYPE"]), "LOB_TYPE")
        self.assertIsNone(D.pick_product_field(["NAME", "PRODUCT_ID"]))
        smp = {"JENIS": ["FTTT", "FTTH", "FTTT"], "NAME": ["A", "B", "C"]}
        self.assertEqual(D.pick_product_field(["NAME", "JENIS"], smp, ["fttt"]), "JENIS")
        self.assertIsNone(D.pick_product_field(["NAME", "JENIS"], smp))

    def test_values_normalised(self):
        v, _m, ok = D.choose_values({"FTT T": 3, "fttt ": 2, "FTTH": 4}, ["FTTT"])
        self.assertTrue(ok)
        self.assertEqual(v, ["FTTT"])
        self.assertEqual(D.norm_value(" f.t-t_t "), "FTTT")


if __name__ == "__main__":
    unittest.main()
