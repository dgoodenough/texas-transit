"""The urban layer's registry and ridership constants (urban/metros.json, study/urban_metros.py)."""
import json
import math
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RegistryTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8") as f:
            self.reg = json.load(f)
        self.by = {m["id"]: m for m in self.reg["metros"]}

    def test_every_texas_metro_but_dfw_with_a_per_resident_budget(self):
        self.assertEqual(len(self.by), 24)   # McAllen and Brownsville-Harlingen as one Valley
        self.assertNotIn("19100", {m["cbsa"] for m in self.reg["metros"]})
        for m in self.reg["metros"]:
            years = 75 if m.get("buildout") or m.get("policies") else 30   # build-out and policy metros: DFW's whole horizon
            self.assertAlmostEqual(m["budget_musd"], 2300 * m["texas_pop"] / 7_468_799 * years, delta=1)
        self.assertEqual(self.by["texarkana"]["state_fips"], ["05", "48"])   # whole CBSA, Texas budget
        self.assertEqual({m["id"] for m in self.reg["metros"] if m.get("policies")},
                         {"houston", "austin", "san-antonio", "el-paso"})

    def test_constants_follow_the_houston_slope(self):
        cal = self.reg["_calibration"]
        self.assertIn("calibration", self.by["houston"])
        h = cal["fits"][0]
        self.assertAlmostEqual(cal["slope_k"], (h["asc"] - cal["asc_dfw"]) / h["ln_share_ratio"], places=3)
        shares = {}
        with open(os.path.join(ROOT, "data", "urban", "acs_transit_share_cbsa.csv"), encoding="utf-8") as f:
            next(f)
            for line in f:
                v = line.rstrip("\n").rsplit(",", 4)
                shares[v[0].split(",")[0]] = float(v[-1])
        for m in self.reg["metros"]:
            if m["id"] == "houston":
                continue
            w = m.get("cbsa_pop") or {m["cbsa"]: 1.0}           # the Valley: its CBSAs' shares weighted by people
            s = max(sum(shares[c] * v for c, v in w.items()) / sum(w.values()), 0.001)
            want = cal["asc_dfw"] + cal["slope_k"] * math.log(s / cal["share_dfw"])
            self.assertAlmostEqual(m["ridership_asc"]["asc"], want, places=3)


if __name__ == "__main__":
    unittest.main()
