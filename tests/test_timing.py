"""The timing step (study/timing.py) and the travellers' gain (texas/intercity.py logsum_gain)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "study"))
from texas import intercity as ic  # noqa: E402
import timing  # noqa: E402


def project(pid, capital, benefit, build=2, after=(), opex=0.0, fares=0.0):
    return {"id": pid, "layer": "hsr", "capital": capital, "benefit": benefit, "opex": opex, "fares": fares,
            "build": build, "after": list(after), "base_year": 2050}


class GainTests(unittest.TestCase):
    def test_no_rail_no_gain_and_small_share_gain_is_about_the_share(self):
        self.assertEqual(ic.logsum_gain(0.9, 0.1, 0.0, 0.6), 0.0)
        g = ic.logsum_gain(0.95, 0.05, 0.01, 1.0)
        r = ic.nested_split(0.95, 0.05, 0.01, 1.0)[2]
        self.assertAlmostEqual(g, r, delta=0.1 * r)
        self.assertGreater(ic.logsum_gain(0.8, 0.2, 0.5, 0.6), ic.logsum_gain(0.8, 0.2, 0.1, 0.6))


class ScheduleTests(unittest.TestCase):
    def test_urban_trajectory_is_relative_to_2050_and_linear_between_runs(self):
        s = {"trips": 1100, "trips_today": 100,
             "future": {"2050": {"trips": 2200, "trips_today_lines": 200}, "2100": {"trips": 3300, "trips_today_lines": 300}}}
        base, traj, year = timing.urban_trajectory(s)
        self.assertEqual((base, year), (2000, 2050))
        self.assertAlmostEqual(traj[2050], 1.0)
        self.assertAlmostEqual(traj[2026], 0.5)
        self.assertAlmostEqual(traj[2075], 1.25)
        self.assertAlmostEqual(traj[2100], 1.5)
        base, traj, year = timing.urban_trajectory({"trips": 1100, "trips_today": 100})   # no future runs: as before
        self.assertEqual((base, traj, year), (1000, None, 2026))

    def test_ratio_counts_operating_deficit_as_cost(self):
        a = project("a", 1000, 100)
        b = project("b", 1000, 100, opex=50, fares=10)
        timing.ratio(a)
        timing.ratio(b)
        self.assertAlmostEqual(a["bcr"], 100 * timing.PV_FACTOR / 1000)
        self.assertAlmostEqual(b["bcr"], 100 * timing.PV_FACTOR / (1000 + 40 * timing.PV_FACTOR))

    def test_best_first_within_the_budget_and_dependents_open_after(self):
        ps = [project("low", 500, 10), project("high", 500, 100), project("child", 300, 1000, build=1, after=["low"])]
        built, spend = timing.schedule(ps, 200)
        by = {p["id"]: p for p in ps}
        self.assertLessEqual(by["high"]["start"], by["low"]["start"])          # better ratio first
        self.assertGreaterEqual(by["child"]["open"], by["low"]["open"])        # opens no earlier than its parent
        cum_b = cum_s = 0.0
        for y in timing.YEARS:                                                  # never borrows
            cum_b += 200
            cum_s += spend[y]
            self.assertLessEqual(cum_s, cum_b + 1e-6)


class WiderAndLandTaxTests(unittest.TestCase):
    def test_wider_benefits_raise_the_ratio_but_not_the_users_ratio(self):
        a = project("a", 1000, 50)
        b = dict(project("b", 1000, 50), wider=20.0, agglom=10.0)
        timing.ratio(a)
        timing.ratio(b)
        self.assertAlmostEqual(a["bcr_users"], b["bcr_users"])
        self.assertAlmostEqual(b["bcr"], 80 * timing.PV_FACTOR / 1000)

    def test_land_tax_bond_is_the_annuity_of_the_yearly_tax_and_rail_beats_brt(self):
        yr, bond = timing.land_tax(10000, 5000, "metro")
        lt = timing.LT
        value = 10000 * lt["value_per_resident"] + 5000 * lt["value_per_job"]
        self.assertAlmostEqual(yr, value * (lt["uplift"]["metro"] * lt["tirz_tax_rate"] + lt["pid_rate"]) / 1e6)
        self.assertAlmostEqual(bond, yr * timing.annuity(lt["bond_rate"], lt["years"]))
        self.assertGreater(yr, timing.land_tax(10000, 5000, "brt")[0])

    def test_bonds_lower_the_budget_draw(self):
        ps = [dict(project("a", 1000, 100, build=1), bond=400.0)]
        built, spend = timing.schedule(ps, 10000)
        self.assertAlmostEqual(sum(spend.values()), 600.0)

    def test_dfw_layer_spends_its_plan_and_the_state_gets_the_rest(self):
        dfw, plan, _ = timing.dfw_layer()
        budget = timing.other_budget(dfw)
        for y in timing.YEARS:
            self.assertAlmostEqual(budget[y], timing.STATE_MUSD - dfw[y]["spend"] + dfw[y]["bond"])
        self.assertGreater(dfw[2050]["trips_day"], 0)   # the plan adds trips over the current track


if __name__ == "__main__":
    unittest.main()
