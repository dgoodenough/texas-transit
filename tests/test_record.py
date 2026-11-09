"""Phase 5: the decade review and the plan's record (study/decade_review.py, study/plan_record.py)."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "study"))


class RecordTests(unittest.TestCase):
    def setUp(self):
        p = os.path.join(ROOT, "docs", "data", "timeline.json")
        if not os.path.exists(p):
            self.skipTest("docs/data/timeline.json not built")
        self.T = json.load(open(p, encoding="utf-8"))

    def test_review_gates(self):
        import decade_review
        rows = decade_review.review(self.T, "whole_map")
        self.assertTrue(rows)
        for r in rows:
            self.assertIn(r["gate3"], ("pass", "designated", "fail"))
            if r["id"] in self.T["connectivity"]:
                self.assertEqual(r["gate3"] == "pass" or r["gate3"] == "designated", True, r["id"])
            if r["gate2"] == "hold":
                self.assertGreater(r["slip_to"], r["start"])

    def test_record_is_current(self):
        """The generated section of study/hsr_buildout.md matches what the model's outputs give now."""
        import plan_record
        text = open(plan_record.DOC, encoding="utf-8").read()
        self.assertIn(plan_record.START, text)
        a, b = text.index(plan_record.START), text.index(plan_record.END) + len(plan_record.END)
        self.assertEqual(text[a:b], plan_record.record(self.T), "rerun python study/plan_record.py")


if __name__ == "__main__":
    unittest.main()
