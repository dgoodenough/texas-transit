"""The cross-border line study (study/cross_border.py)."""
import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "study"))
import cross_border as cb  # noqa: E402


class CrossBorderTests(unittest.TestCase):
    def test_juarez_is_placed_south_of_the_river(self):
        lat, lon, pop, is_mx = cb.cells()
        self.assertAlmostEqual(pop.sum(), cb.JUAREZ_POP, delta=1)
        self.assertTrue((pop[~is_mx] == 0).all())
        # downtown El Paso is on the US side, Juárez's centre on the Mexican side
        near = lambda p: int(np.argmin((lat - p[0]) ** 2 + ((lon - p[1]) * 0.85) ** 2))  # noqa: E731
        self.assertFalse(is_mx[near(cb.DOWNTOWN_EP)])
        self.assertTrue(is_mx[near((31.73, -106.47))])

    def test_crossers_start_near_the_bridge_and_walk_if_close(self):
        lat, lon, pop, is_mx = cb.cells()
        w, d = cb.origins(lat, lon, pop, is_mx)
        self.assertAlmostEqual(w.sum(), 1.0)
        self.assertLess(float((w * d).sum()), 8.0)
        t = cb.today_minutes(np.array([0.5, 1.5, 6.0]))
        self.assertLess(t[0], t[1])
        self.assertLess(t[1], t[2])

    def test_the_line_beats_the_bus_near_its_stations(self):
        lat, lon = np.array([31.70]), np.array([-106.45])
        t1 = cb.line_minutes(lat, lon, [(31.70, -106.45)], [6.0], "brt")
        self.assertLess(t1[0], cb.today_minutes(np.array([6.0]))[0])
        far = cb.line_minutes(lat, lon, [(31.60, -106.30)], [6.0], "brt")
        self.assertTrue(np.isinf(far[0]))


if __name__ == "__main__":
    unittest.main()
