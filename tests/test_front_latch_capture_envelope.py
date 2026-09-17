import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_front_latch_capture_envelope as capture

ASSET = ROOT / "assets/modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
INTERFACE_PATH = ASSET / "front-latch-pivot-interface-001.json"
POLICY_PATH = ASSET / "front-latch-capture-envelope-001.json"

HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
INTERFACE = json.loads(INTERFACE_PATH.read_text(encoding="utf-8"))
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))


class FrontLatchCaptureEnvelopeTests(unittest.TestCase):
    def verify(self, policy=POLICY, interface=INTERFACE):
        return capture.verify(
            HOST,
            interface,
            policy,
            host_sha256=capture.sha256(HOST_PATH),
            interface_sha256=capture.sha256(INTERFACE_PATH),
        )

    def test_source_owns_true_proof_volume_capture_transition(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_TO_CLEARANCE_ENVELOPE")
        self.assertEqual(receipt["station_count"], 2)
        self.assertAlmostEqual(receipt["capture_transition_deg"], 9.2647903335512, places=10)
        self.assertAlmostEqual(receipt["z_aabb_only_transition_deg"], 48.66480246428278, places=10)
        self.assertGreater(receipt["z_aabb_minus_capture_transition_deg"], 39.0)
        self.assertAlmostEqual(receipt["review_release_z_axis_separation_m"], 0.0015728659779459, places=12)
        self.assertEqual(receipt["bilateral_capture_transition_residual_deg"], 0.0)
        self.assertEqual(receipt["bilateral_z_aabb_transition_residual_deg"], 0.0)
        self.assertFalse(receipt["host_source_geometry_changed"])
        truth = receipt["truth_boundary"]
        self.assertTrue(truth["intentional_neutral_engagement_overlap_preserved"])
        self.assertTrue(truth["proof_volume_capture_transition_observed"])
        self.assertTrue(truth["z_aabb_only_is_not_capture_threshold"])
        self.assertFalse(truth["sampled_release_path_reentry_observed"])
        self.assertFalse(truth["physical_latch_capture_or_retention_proven"])
        self.assertFalse(truth["continuous_full_assembly_collision_freedom_proven"])
        self.assertFalse(truth["animation_timing_owned"])
        self.assertFalse(truth["runtime_controller_owned"])

    def test_rejects_z_aabb_as_capture_model(self):
        bad = copy.deepcopy(POLICY)
        bad["contact_model"]["intersection_method"] = "Z_AABB_ONLY"
        with self.assertRaisesRegex(AssertionError, "CONTACT_MODEL_DRIFT"):
            self.verify(policy=bad)

    def test_rejects_false_contact_transition_range(self):
        bad = copy.deepcopy(POLICY)
        bad["contact_model"]["expected_contact_transition_deg_range"] = [48.0, 49.0]
        with self.assertRaisesRegex(AssertionError, "CONTACT_TRANSITION_RANGE_MISMATCH"):
            self.verify(policy=bad)

    def test_rejects_release_endpoint_separation_inflation(self):
        bad = copy.deepcopy(POLICY)
        bad["contact_model"]["minimum_review_release_z_axis_separation_m"] = 0.002
        with self.assertRaisesRegex(AssertionError, "RELEASE_ENDPOINT_Z_SEPARATION_BELOW_MINIMUM"):
            self.verify(policy=bad)

    def test_rejects_authority_inflation(self):
        bad = copy.deepcopy(POLICY)
        bad["authority"]["physical_latch_retention_owned"] = True
        with self.assertRaisesRegex(AssertionError, "AUTHORITY_INFLATION"):
            self.verify(policy=bad)

    def test_rejects_interface_identity_drift(self):
        bad = copy.deepcopy(POLICY)
        bad["pivot_interface"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "PIVOT_INTERFACE_IDENTITY_DRIFT"):
            self.verify(policy=bad)


if __name__ == "__main__":
    unittest.main()
