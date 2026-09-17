import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_front_latch_mechanical_state_policy as mechanical

ASSET = ROOT / "assets/modular-equipment-case-001"
INTERFACE_PATH = ASSET / "front-latch-pivot-interface-001.json"
POLICY_PATH = ASSET / "front-latch-mechanical-state-policy-001.json"

INTERFACE = json.loads(INTERFACE_PATH.read_text(encoding="utf-8"))
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

ANIMATION_HEAD = "9725eb2ddde3b79c73bfdbbaef7c0e14da6af1a7"
INTERFACE_HEAD = "6086f39a3da344c57a68653f90d040e03e04cec2"
ANIMATION_GUARD_SHA256 = "cfc75666bc15eb94301a0dd03743265b37595aab4cd5aebae2c3aed617f80fb0"
ANIMATION_GUARD = {
    "schema": "axm.object-animation-mechanical-phase-guard/v0.1",
    "contract_id": "lid-latch-continuous-moving-phase-guard-001",
    "asset_id": "modular-equipment-case-001",
    "rigging_dependency": {
        "exact_head": "44e0a56872a823cf768c749672116fd026b1ef5e",
        "artifact_id": 10483747546,
        "artifact_sha256": "2785d67b29325a4041f5761033b56d07b93aa30ca9645db05434d432892b4a9e",
        "required_latch_angle_deg": 50.0,
        "required_lid_open_interval_deg": [0.0, 100.0],
        "minimum_continuous_separation_lower_bound_m": 0.0015728659779459253,
    },
    "truth_boundary": {
        "continuous_moving_lid_keeper_lever_clearance_may_be_composed": True,
        "continuous_latch_release_clearance_proven": False,
        "continuous_latch_reengagement_clearance_proven": False,
        "physical_latch_capture_or_retention_proven": False,
        "runtime_controller_accepted": False,
        "gameplay_accepted": False,
    },
}


class FrontLatchMechanicalStatePolicyTests(unittest.TestCase):
    def verify(self, policy=POLICY, animation_guard=ANIMATION_GUARD):
        return mechanical.verify(
            INTERFACE,
            animation_guard,
            policy,
            interface_sha256=mechanical.sha256(INTERFACE_PATH),
            animation_guard_sha256=ANIMATION_GUARD_SHA256,
            observed_interface_head=INTERFACE_HEAD,
            observed_animation_head=ANIMATION_HEAD,
        )

    def test_source_owns_bounded_mechanical_admissibility_without_timing(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_FRONT_LATCH_MECHANICAL_STATE_GUARD")
        self.assertEqual(receipt["mechanical_state_count"], 4)
        self.assertFalse(receipt["host_geometry_changed"])
        self.assertFalse(receipt["animation_motion_authorship_changed"])
        self.assertAlmostEqual(receipt["source_interface"]["review_release_angle_deg"], 50.0)
        self.assertEqual(receipt["downstream_observation"]["moving_lid_interval_deg"], [0.0, 100.0])
        self.assertGreaterEqual(
            receipt["downstream_observation"]["continuous_clearance_lower_bound_m"],
            receipt["source_interface"]["minimum_release_separation_m"],
        )
        truth = receipt["truth_boundary"]
        self.assertTrue(truth["intentional_neutral_engagement_overlap_preserved"])
        self.assertFalse(truth["continuous_latch_release_clearance_proven"])
        self.assertFalse(truth["continuous_latch_reengagement_clearance_proven"])
        self.assertFalse(truth["animation_timing_owned"])
        self.assertFalse(truth["runtime_controller_owned"])

    def test_rejects_unreleased_lid_motion(self):
        bad = copy.deepcopy(POLICY)
        bad["mechanical_states"][0]["lid_motion_allowed"] = True
        with self.assertRaisesRegex(AssertionError, "UNRELEASED_LID_MOTION_ALLOWED"):
            self.verify(policy=bad)

    def test_rejects_false_release_clearance_promotion(self):
        bad = copy.deepcopy(POLICY)
        bad["source_rules"]["continuous_release_clearance_claimed"] = True
        with self.assertRaisesRegex(AssertionError, "FALSE_RELEASE_CLEARANCE_PROMOTION"):
            self.verify(policy=bad)

    def test_rejects_engagement_semantic_loss(self):
        bad = copy.deepcopy(POLICY)
        bad["mechanical_states"][0]["contact_semantic"] = "COLLISION_DEFECT"
        with self.assertRaisesRegex(AssertionError, "ENGAGEMENT_SEMANTIC_LOSS"):
            self.verify(policy=bad)

    def test_rejects_rigging_identity_drift(self):
        bad = copy.deepcopy(ANIMATION_GUARD)
        bad["rigging_dependency"]["exact_head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "RIGGING_HEAD_DRIFT"):
            self.verify(animation_guard=bad)


if __name__ == "__main__":
    unittest.main()
