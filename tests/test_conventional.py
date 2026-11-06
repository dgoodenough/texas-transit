"""Conventional rail (texas/conventional.py) and the timetable wait and border time in texas/intercity.py."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from texas import conventional as cv, intercity as ic  # noqa: E402


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.p = ic.load_params()
        self.svc = self.p["conventional"]

    def test_headway_and_wait_follow_the_timetable(self):
        one, four = cv.service(self.svc, 1), cv.service(self.svc, 4)
        self.assertAlmostEqual(one["headway_min"], self.svc["service_hours"] * 60)
        self.assertAlmostEqual(four["headway_min"], one["headway_min"] / 4)
        self.assertLess(ic.wait_min(four), ic.wait_min(one))
        self.assertLessEqual(ic.wait_min(one), self.svc["max_wait_min"])
        self.assertEqual(ic.wait_min({"headway_min": 30, "max_wait_min": 30}), 15)   # HSR: half the headway

    def test_more_trains_cost_more_and_existing_stops_less(self):
        self.assertGreater(cv.capital_musd("I20", 4, self.svc), cv.capital_musd("I20", 2, self.svc))
        self.assertGreater(cv.trainsets("I20", 4, self.svc), cv.trainsets("I20", 2, self.svc))
        self.assertAlmostEqual(cv.opex_musd("I20", 4), 2 * cv.opex_musd("I20", 2))
        # Monterrey carries the border station
        mty = cv.capital_musd("MTY", 2, self.svc)
        without = mty - cv.BORDER_STATION
        self.assertGreater(mty, without)

    def test_border_time_counts_for_car_and_rail(self):
        stations = {"A": (29.4, -98.5), "B": (25.7, -100.3)}
        net = ic.RailNetwork(stations, [("A", "B", 500.0)], cv.service(self.svc, 4))
        za = {"at": (29.4, -98.5), "parts": []}
        zb = {"at": (25.7, -100.3), "parts": []}
        open_border = net.odds(za, zb, "nonwork", self.p)
        slow = net.odds(za, dict(zb, border_min=60), "nonwork", self.p)
        self.assertGreater(open_border, 0)
        # the same hour for both: rail's odds fall (its hour is out-of-vehicle time, weighted more) but not to zero
        self.assertLess(slow, open_border)
        self.assertGreater(slow, 0.2 * open_border)


class HsrUnchangedTests(unittest.TestCase):
    def test_hsr_wait_is_still_half_the_headway(self):
        p = ic.load_params()
        self.assertNotIn("wait_share", p["hsr"])
        self.assertEqual(ic.wait_min(p["hsr"]), min(p["hsr"]["headway_min"] / 2, p["hsr"]["max_wait_min"]))


if __name__ == "__main__":
    unittest.main()
