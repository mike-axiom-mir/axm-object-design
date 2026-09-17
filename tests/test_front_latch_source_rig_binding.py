import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_front_latch_source_rig_binding as rig

ASSET = ROOT / "assets/modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
OWNERSHIP_PATH = ASSET / "front-latch-ownership-001.json"
INTERFACE_PATH = ASSET / "front-latch-pivot-interface-001.json"
BINDING_PATH = ASSET / "front-latch-source-rig-binding-003.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
OWNERSHIP = json.loads(OWNERSHIP_PATH.read_text(encoding="utf-8"))
INTERFACE = json.loads(INTERFACE_PATH.read_text(encoding="utf-8"))
BINDING = json.loads(BINDING_PATH.read_text(encoding="utf-8"))

HISTORICAL_PLAN = {
    "host_source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
    "ownership_donor_head": "d3fa10a270faae7925811f44f03381fe5c5d0215",
    "pivot_rule": "source_x__panel_negative_y_face__lever_min_z",
    "joint_axis": [1.0, 0.0, 0.0],
    "review_angle_min_deg": 0.0,
    "review_angle_max_deg": 50.0,
}

CAPTURE_POLICY = {
    "schema": "axm.object-front-latch-capture-envelope/v0.1",
    "asset_id": "modular-equipment-case-001",
    "host_source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
    "pivot_interface": {"sha256": rig.EXPECTED_INTERFACE_SHA256},
    "contact_model": {
        "intersection_method": "POSITIVE_X_INTERVAL_OVERLAP_PLUS_EXACT_YZ_ORIENTED_RECTANGLE_SAT",
    },
    "source_semantics": {
        "z_aabb_transition": "BROAD_PHASE_AXIS_SEPARATION_ONLY_NOT_CAPTURE_THRESHOLD",
    },
    "authority": {
        "hard_surface_owns_source_contact_intent": True,
        "hard_surface_owns_proof_volume_capture_envelope": True,
        "animation_timing_owned": False,
        "rigging_motion_authorship_owned": False,
        "runtime_controller_owned": False,
        "physics_owned": False,
        "physical_latch_retention_owned": False,
        "manufacturing_fit_owned": False,
    },
}

CAPTURE_RECEIPT = {
    "result": rig.EXPECTED_CAPTURE_RESULT,
    "host_source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
    "pivot_interface_sha256": rig.EXPECTED_INTERFACE_SHA256,
    "contact_model": "POSITIVE_X_INTERVAL_OVERLAP_PLUS_EXACT_YZ_ORIENTED_RECTANGLE_SAT",
    "capture_transition_deg": 9.264790333551197,
    "z_aabb_only_transition_deg": 48.66480246428277,
    "z_aabb_minus_capture_transition_deg": 39.400012130731575,
    "review_release_z_axis_separation_m": 0.0015728659779458698,
    "station_results": [
        {"capture_transition_sample_bracket_deg": [9.25, 9.30]},
        {"capture_transition_sample_bracket_deg": [9.25, 9.30]},
    ],
    "truth_boundary": {
        "z_aabb_only_is_not_capture_threshold": True,
        "sampled_release_path_reentry_observed": False,
        "physical_latch_capture_or_retention_proven": False,
        "manufacturing_fit_or_tolerance_proven": False,
        "dynamic_release_or_reengagement_forces_proven": False,
        "continuous_full_assembly_collision_freedom_proven": False,
        "animation_timing_owned": False,
        "runtime_controller_owned": False,
        "physics_owned": False,
    },
}


class FrontLatchSourceRigBindingTests(unittest.TestCase):
    def verify(
        self,
        binding=BINDING,
        interface=INTERFACE,
        capture_policy=CAPTURE_POLICY,
        capture_receipt=CAPTURE_RECEIPT,
        capture_blob_sha=rig.EXPECTED_CAPTURE_POLICY_BLOB_SHA,
        historical_plan=HISTORICAL_PLAN,
    ):
        return rig.verify(
            HOST,
            OWNERSHIP,
            interface,
            historical_plan,
            capture_policy,
            capture_receipt,
            binding,
            host_sha=rig.sha256(HOST_PATH),
            ownership_sha=rig.sha256(OWNERSHIP_PATH),
            interface_sha=rig.EXPECTED_INTERFACE_SHA256,
            historical_plan_sha=rig.EXPECTED_HISTORICAL_PLAN_SHA256,
            capture_policy_blob_sha=capture_blob_sha,
            binding_sha=rig.sha256(BINDING_PATH),
        )

    def test_exact_source_capture_envelope_rebinds_rigging_boundary(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_FRONT_LATCH_RIG_CAPTURE_ENVELOPE_REBIND")
        self.assertEqual(receipt["pose_samples_deg"], [0.0, 9.25, 9.30, 25.0, 48.65, 48.70, 50.0])
        self.assertAlmostEqual(receipt["source_capture_transition_deg"], 9.264790333551197, places=11)
        self.assertAlmostEqual(receipt["z_aabb_only_transition_deg"], 48.66480246428277, places=11)
        self.assertGreater(receipt["z_aabb_minus_capture_transition_deg"], 39.0)
        self.assertEqual(
            receipt["historical_interface_threshold_reclassified_as"],
            "Z_AABB_BROAD_PHASE_ONLY_NOT_CAPTURE_THRESHOLD",
        )
        self.assertAlmostEqual(receipt["historical_interface_threshold_deg"], receipt["z_aabb_only_transition_deg"], places=10)
        self.assertFalse(receipt["host_geometry_changed"])
        self.assertFalse(receipt["rig_pivots_changed"])
        self.assertFalse(receipt["lever_geometry_changed"])
        self.assertFalse(receipt["motion_envelope_retuned"])
        self.assertLessEqual(receipt["maximum_rigid_pairwise_distance_drift_m"], 1e-12)
        self.assertLessEqual(receipt["maximum_pivot_drift_m"], 1e-12)
        self.assertLessEqual(receipt["maximum_bilateral_pose_z_overlap_residual_m"], 1e-12)
        left = receipt["station_results"][0]["pose_results"]
        self.assertEqual(left[2]["relative_to_source_capture_transition"], "AFTER_CAPTURE_BOUNDARY")
        self.assertEqual(left[2]["relative_to_z_aabb_transition"], "BEFORE_OR_AT_Z_AABB_BOUNDARY")
        self.assertGreater(left[2]["keeper_axis_overlap_m"]["z"], 0.0)
        self.assertGreater(left[4]["keeper_axis_overlap_m"]["z"], 0.0)
        self.assertLess(left[5]["keeper_axis_overlap_m"]["z"], 0.0)

    def test_rejects_source_authority_head_drift(self):
        bad = copy.deepcopy(BINDING)
        bad["source_mechanical_authority"]["head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "source mechanical authority head drift"):
            self.verify(binding=bad)

    def test_rejects_materialized_capture_policy_identity_drift(self):
        with self.assertRaisesRegex(AssertionError, "materialized capture-envelope blob identity drift"):
            self.verify(capture_blob_sha="0" * 40)

    def test_rejects_z_aabb_relabelled_as_capture_truth(self):
        bad = copy.deepcopy(CAPTURE_RECEIPT)
        bad["truth_boundary"]["z_aabb_only_is_not_capture_threshold"] = False
        with self.assertRaisesRegex(AssertionError, "lost broad-phase distinction"):
            self.verify(capture_receipt=bad)

    def test_rejects_historical_plan_repromotion(self):
        bad = copy.deepcopy(BINDING)
        bad["historical_rigging_observation"]["role"] = "CURRENT_INTERFACE_AUTHORITY"
        with self.assertRaisesRegex(AssertionError, "historical Rigging role drift"):
            self.verify(binding=bad)

    def test_rejects_source_owned_pivot_drift(self):
        bad = copy.deepcopy(INTERFACE)
        bad["stations"][0]["pivot_origin_m"][2] += 0.001
        with self.assertRaisesRegex(AssertionError, "pivot origin drift from source rule"):
            self.verify(interface=bad)


if __name__ == "__main__":
    unittest.main()
