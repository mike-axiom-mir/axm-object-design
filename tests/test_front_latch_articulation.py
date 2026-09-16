import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_front_latch_articulation as rig

HOST_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
OWNERSHIP_PATH = ROOT / "assets/modular-equipment-case-001/front-latch-ownership-001.json"
PLAN_PATH = ROOT / "assets/modular-equipment-case-001/front-latch-articulation-001.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
OWNERSHIP = json.loads(OWNERSHIP_PATH.read_text(encoding="utf-8"))
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))


class FrontLatchArticulationTests(unittest.TestCase):
    def verify(self, host=HOST, ownership=OWNERSHIP, plan=PLAN, host_sha=None):
        return rig.verify(
            host,
            ownership,
            plan,
            host_sha=host_sha or rig.sha256(HOST_PATH),
            ownership_sha=rig.sha256(OWNERSHIP_PATH),
            plan_sha=rig.sha256(PLAN_PATH),
        )

    def test_exact_bilateral_articulation_reaches_bounded_keeper_separation(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_BOUNDED_FRONT_LATCH_LEVER_ARTICULATION")
        self.assertEqual(receipt["pose_samples_deg"], [0.0, 25.0, 50.0])
        self.assertAlmostEqual(receipt["continuous_keeper_z_separation_threshold_deg"], 48.66480246428274, places=9)
        self.assertAlmostEqual(receipt["terminal_keeper_z_separation_m"], 0.0015728659779459, places=12)
        self.assertAlmostEqual(receipt["bilateral_pivot_residual_m"], 0.0, places=12)
        self.assertAlmostEqual(receipt["bilateral_threshold_residual_deg"], 0.0, places=12)
        self.assertAlmostEqual(receipt["bilateral_terminal_separation_residual_m"], 0.0, places=12)
        for row in receipt["station_results"]:
            self.assertAlmostEqual(row["maximum_rigid_pairwise_distance_drift_m"], 0.0, places=12)
            self.assertAlmostEqual(row["maximum_pivot_drift_m"], 0.0, places=12)
            self.assertGreater(min(row["pose_results"][0]["keeper_axis_overlap_m"].values()), 0.0)
            self.assertLess(row["pose_results"][-1]["keeper_axis_overlap_m"]["z"], 0.0)

    def test_rejects_source_identity_drift(self):
        bad = copy.deepcopy(PLAN)
        bad["host_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "host source identity mismatch"):
            self.verify(plan=bad)

    def test_rejects_ownership_donor_drift(self):
        bad = copy.deepcopy(PLAN)
        bad["ownership_donor_head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "ownership donor head drift"):
            self.verify(plan=bad)

    def test_rejects_pivot_rule_drift(self):
        bad = copy.deepcopy(PLAN)
        bad["pivot_rule"] = "guess_from_visual"
        with self.assertRaisesRegex(AssertionError, "unsupported pivot derivation rule"):
            self.verify(plan=bad)

    def test_rejects_review_envelope_that_does_not_reach_declared_release_bound(self):
        bad = copy.deepcopy(PLAN)
        bad["pose_samples_deg"] = [0.0, 22.5, 45.0]
        bad["review_angle_max_deg"] = 45.0
        with self.assertRaisesRegex(AssertionError, "review envelope drift"):
            self.verify(plan=bad)

    def test_rejects_impossible_terminal_separation_requirement(self):
        bad = copy.deepcopy(PLAN)
        bad["minimum_terminal_keeper_axis_separation_m"] = 0.01
        with self.assertRaisesRegex(AssertionError, "terminal keeper separation is below declared bound"):
            self.verify(plan=bad)


if __name__ == "__main__":
    unittest.main()
