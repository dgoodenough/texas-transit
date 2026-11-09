"""The statewide map's data (tools/build_state_map.py, texas/hsr_alignments.json)."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from texas import hsr  # noqa: E402


class AlignmentTests(unittest.TestCase):
    def test_waypoints_name_real_station_pairs_of_their_corridor(self):
        al = json.load(open(os.path.join(ROOT, "texas", "hsr_alignments.json"), encoding="utf-8"))
        pairs = {f"{a}|{b}" for _, sts in hsr.CORRIDORS.values() for a, b in zip(sts, sts[1:])}
        pairs |= {f"{b}|{a}" for k in list(pairs) for a, b in [k.split("|")]}
        for cid, segs in al["waypoints"].items():
            for k, pts in segs.items():
                self.assertIn(k, pairs, cid)
                for la, lo in pts:   # in or next to Texas
                    self.assertTrue(25 < la < 36.5 and -107 < lo < -89, (cid, k))

    def test_state_map_has_every_corridor_and_drawn_lengths_near_the_model(self):
        p = os.path.join(ROOT, "docs", "data", "state.json")
        if not os.path.exists(p):
            self.skipTest("docs/data/state.json not built")
        d = json.load(open(p, encoding="utf-8"))
        self.assertEqual({h["id"] for h in d["hsr"]}, {f"hsr:{k}" for k in hsr.CORRIDORS})
        for h in d["hsr"]:
            self.assertTrue(0.9 < h["km_map"] / h["km_model"] < 1.1, h["id"])   # the model now uses the drawn km
        tc = next(h for h in d["hsr"] if h["id"] == "hsr:TC")
        self.assertGreater(len(tc["pts"]), 20)
        self.assertTrue(d["lines"])


if __name__ == "__main__":
    unittest.main()


class LeverTests(unittest.TestCase):
    """Phase 4: the "what it takes" panel reads a precomputed grid that must agree with the scenarios."""

    def setUp(self):
        p = os.path.join(ROOT, "docs", "data", "timeline.json")
        if not os.path.exists(p):
            self.skipTest("docs/data/timeline.json not built")
        self.T = json.load(open(p, encoding="utf-8"))

    def test_every_lever_on_is_the_whole_map(self):
        T = self.T
        on = T["levers"]["|".join("central" if k == "costs" else "1" for k in T["lever_names"])]
        when = T["scenarios"]["whole_map"]["when"]
        for pid in T["connectivity"]:
            self.assertEqual(on["opens"].get(pid), (when.get(pid) or [None, None])[1], pid)

    def test_a_branch_waits_for_its_trunk(self):
        T = self.T
        when = T["scenarios"]["whole_map"]["when"]
        P = {p["id"]: p for p in T["whole_map_projects"]}
        for pid in T["connectivity"]:
            if pid not in when:
                continue
            for d in P[pid].get("after", []):
                if d in when:
                    self.assertGreaterEqual(when[pid][0], when[d][1] + 3, (pid, d))

    def test_the_grid_covers_every_combination(self):
        self.assertEqual(len(self.T["levers"]), 2 ** (len(self.T["lever_names"]) - 1) * 2)
