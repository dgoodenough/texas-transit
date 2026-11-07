"""The intercity mode choice (texas/intercity.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from texas import intercity as ic  # noqa: E402


class SplitTests(unittest.TestCase):
    def test_no_rail_keeps_todays_shares(self):
        self.assertEqual(ic.nested_split(0.9, 0.1, 0.0, 0.6), (0.9, 0.1, 0.0))

    def test_shares_add_up_and_rail_draws_more_from_air_when_nested(self):
        for scale in (0.4, 0.6, 1.0):
            c, a, r = ic.nested_split(0.8, 0.2, 0.3, scale)
            self.assertAlmostEqual(c + a + r, 1.0)
        c1, a1, _ = ic.nested_split(0.8, 0.2, 0.3, 1.0)
        c6, a6, _ = ic.nested_split(0.8, 0.2, 0.3, 0.6)
        self.assertLess(a6 / 0.2, a1 / 0.2)    # nested: air keeps less of its share
        self.assertGreater(c6 / 0.8, c1 / 0.8)  # and car keeps more

    def test_plain_logit_takes_proportionally(self):
        c, a, r = ic.nested_split(0.8, 0.2, 0.25, 1.0)
        self.assertAlmostEqual(c / a, 4.0)


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.p = ic.load_params()
        self.stations = {"A": (30.0, -97.0), "B": (31.0, -97.0), "C": (32.0, -97.0)}
        links = [("A", "B", 115.0), ("B", "C", 115.0)]
        self.net = ic.RailNetwork(self.stations, links, self.p["hsr"])

    def test_path_stops_at_intermediate_stations(self):
        t, track = self.net.path("A", "C")
        self.assertAlmostEqual(track, 230.0)
        self.assertAlmostEqual(t, 230 / self.p["hsr"]["speed_kmh"] * 60 + self.p["hsr"]["stop_min"])

    def test_zone_far_from_every_station_is_not_served(self):
        near = {"at": (30.0, -97.0), "parts": []}
        far = {"at": (35.0, -97.0), "parts": []}
        self.assertIsNone(self.net.los(near, far, "work", self.p))
        self.assertIsNotNone(self.net.los(near, {"at": (32.0, -97.0), "parts": []}, "work", self.p))

    def test_access_is_averaged_over_a_zones_people(self):
        spread = {"at": (30.0, -97.0), "parts": [((30.0, -97.0), 1), ((30.3, -97.0), 1)]}
        s, d = self.net.station_for(spread)
        self.assertEqual(s, "A")
        self.assertAlmostEqual(d, ic.km((30.0, -97.0), (30.3, -97.0)) / 2, places=3)


class ServicePatternTests(unittest.TestCase):
    """A wye: trunk H - J, branches J - A and J - S, half the trunk's trains on each branch."""

    def setUp(self):
        self.p = ic.load_params()
        self.svc = self.p["hsr"]
        st = {"H": (29.8, -95.5), "J": (29.8, -96.9), "A": (30.3, -97.7), "S": (29.4, -98.5), "D": (32.8, -96.8)}
        links = [("H", "J", 150.0), ("J", "A", 90.0), ("J", "S", 180.0), ("D", "A", 330.0)]
        self.services = [(["H", "J", "A"], 60), (["H", "J", "S"], 60), (["D", "A"], 30)]
        self.net = ic.RailNetwork(st, links, self.svc, services=self.services)
        self.plain = ic.RailNetwork(st, links, self.svc)

    def test_without_patterns_every_trip_has_the_one_headway(self):
        self.assertEqual(self.plain.headway("H", "S"), self.svc["headway_min"])
        self.assertEqual(self.plain.wait("H", "S"), ic.wait_min(self.svc))

    def test_trunk_adds_the_branches_trains_and_branches_have_their_own(self):
        self.assertAlmostEqual(self.net.headway("H", "J"), 30)
        self.assertAlmostEqual(self.net.headway("H", "A"), 60)
        self.assertAlmostEqual(self.net.headway("J", "S"), 60)
        self.assertAlmostEqual(self.net.wait("H", "A"), min(30, self.svc["max_wait_min"]))

    def test_a_trip_no_pattern_serves_waits_for_its_least_frequent_link(self):
        self.assertEqual(self.net.route("D", "H"), ["D", "A", "J", "H"])
        self.assertAlmostEqual(self.net.headway("D", "H"), 60)
        self.assertAlmostEqual(self.net.headway("A", "S"), 60)   # a change at J onto the other branch

    def test_less_frequent_branches_lower_rail_odds(self):
        za = {"at": (29.8, -95.5), "parts": []}
        zb = {"at": (30.3, -97.7), "parts": []}
        self.assertLess(self.net.odds(za, zb, "work", self.p), self.plain.odds(za, zb, "work", self.p))


class DataTests(unittest.TestCase):
    def test_dallas_houston_air_comes_from_the_ticket_sample(self):
        p = ic.load_params()
        zones = ic.load_zones()
        base = ic.base_trips(zones, p)
        dh = base[tuple(sorted(("19100_TX", "26420_TX")))]
        self.assertIsNotNone(dh["air_fare"])
        self.assertGreater(dh["air"], 3000)          # about 2 x 1,737 passengers a day each way
        self.assertGreater(dh["car"], 20000)
        res = ic.run({k: base[k] for k in [tuple(sorted(("19100_TX", "26420_TX")))]}, zones, p)
        r = next(iter(res.values()))
        self.assertAlmostEqual(r["new"]["car"], r["base"]["car"], places=6)   # no network: today unchanged
        self.assertEqual(r["new"]["rail"], 0.0)

    def test_growth_scales_trips_and_keeps_shares(self):
        p = ic.load_params()
        zones = ic.load_zones()
        pair = tuple(sorted(("19100_TX", "26420_TX")))
        base = {pair: ic.base_trips(zones, p)[pair]}
        growth = {z: 1.0 for z in zones}
        growth[pair[0]], growth[pair[1]] = 1.44, 1.0
        r = next(iter(ic.run(base, zones, p, growth=growth).values()))
        today = base[pair]["car"] + base[pair]["air"]
        self.assertAlmostEqual(r["new"]["car"] + r["new"]["air"], today * 1.2, places=6)   # sqrt(1.44 x 1.0)
        self.assertAlmostEqual(r["new"]["air"] / (r["new"]["car"] + r["new"]["air"]),
                               base[pair]["air"] / today, places=9)


if __name__ == "__main__":
    unittest.main()
