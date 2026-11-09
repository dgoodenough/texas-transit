"""Phase 2: the high-speed cost model, service patterns, finance and the whole-map scheduling."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "study"))
from texas import finance, hsr  # noqa: E402
from texas.intercity import km  # noqa: E402


class CostModelTests(unittest.TestCase):
    def setUp(self):
        self.saved = dict(hsr.SETTINGS)

    def tearDown(self):
        hsr.SETTINGS.clear()
        hsr.SETTINGS.update(self.saved)

    def test_flat_settings_reproduce_the_old_cost(self):
        hsr.SETTINGS.update(case="flat", drawn=False, learning=False)
        sts = hsr.CORRIDORS["TC"][1]
        track = sum(km(hsr.point(a), hsr.point(b)) * hsr.TRACK_FACTOR for a, b in zip(sts, sts[1:]))
        st = sum(hsr.STATION_COST[hsr.STATIONS[s][2]] for s in sts)
        self.assertAlmostEqual(hsr.capital_musd(["TC"]), track * hsr.COST_PER_KM + st)

    def test_cases_order_and_lighter_standards_cost_less(self):
        costs = {}
        for c in ("low", "central", "high"):
            hsr.SETTINGS.update(case=c, standards={})
            costs[c] = hsr.capital_musd(["WEST"], built=["BIGC"])
        self.assertLess(costs["low"], costs["central"])
        self.assertLess(costs["central"], costs["high"])
        hsr.SETTINGS.update(case="central", standards={"WEST": "S4"})
        self.assertLess(hsr.capital_musd(["WEST"], built=["BIGC"]), costs["central"])

    def test_learning_needs_kilometres(self):
        hsr.SETTINGS.update(learning=True)
        self.assertEqual(hsr.learning_factor(400), 1.0)
        self.assertAlmostEqual(hsr.learning_factor(1000), 0.9)
        self.assertEqual(hsr.learning_factor(1e7), 0.75)
        hsr.SETTINGS.update(learning=False)
        self.assertEqual(hsr.learning_factor(5000), 1.0)

    def test_slower_standard_slows_the_link(self):
        hsr.SETTINGS.update(standards={"PANH": "S4"})
        self.assertEqual(hsr.link_speed("Lubbock", "Amarillo", ["PANH"]), hsr.STANDARDS["S4"][1])
        hsr.SETTINGS.update(standards={})
        self.assertEqual(hsr.link_speed("Lubbock", "Amarillo", ["PANH"]), hsr.STANDARDS["S1"][1])


class PatternTests(unittest.TestCase):
    def test_through_patterns_once_built_shuttles_before(self):
        part = hsr.services_for(["I10", "TC"])
        self.assertIn((hsr.CORRIDORS["TC"][1], hsr.SHUTTLE_HEADWAY["TC"]), part)
        full = hsr.services_for(["FW", "TC"])
        self.assertIn((["Fort Worth", "Dallas", "Brazos Valley", "Houston"], 30), full)
        self.assertEqual(len(full), 1)   # both corridors covered by the through pattern

    def test_branches_wait_for_trunks(self):
        for cid, deps in hsr.REQUIRES.items():
            for d in deps:
                self.assertIn(d, hsr.CORRIDORS)


class FinanceTests(unittest.TestCase):
    def test_out_of_state_shares(self):
        self.assertGreater(finance.corridor_out_of_state("OKC"), 0.4)
        self.assertGreater(finance.corridor_out_of_state("GULF"), 0.5)
        self.assertEqual(finance.corridor_out_of_state("TC"), 0.0)

    def test_rail_fund_starts_and_grows(self):
        pop = {y: 1.0 + (y - 2025) / 100 for y in range(2020, 2101)}
        self.assertEqual(finance.rail_fund(2029, pop), 0.0)
        self.assertGreater(finance.rail_fund(2060, pop), finance.rail_fund(2030, pop))


class TrunkFirstTests(unittest.TestCase):
    def test_a_branch_never_comes_before_its_trunk(self):
        import timing
        ps = [{"id": "b", "after": ["a"], "bcr": 5.0}, {"id": "a", "after": [], "bcr": 1.0},
              {"id": "c", "after": [], "bcr": 3.0}]
        order = [p["id"] for p in timing.trunk_first(ps)]
        self.assertLess(order.index("a"), order.index("b"))
        self.assertEqual(order[0], "c")


if __name__ == "__main__":
    unittest.main()
