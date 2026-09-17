from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_hinge_knuckle_rig_parent_binding import (  # noqa: E402
    LID_RIG_HEAD,
    OWNER_STACK_BLOB,
    OWNER_STACK_HEAD,
    PREVIOUS_RIGGING_HEAD,
    RESULT,
    SOURCE_SHA256,
    sha256_file,
    verify,
)

OWNER_STACK = {
    "schema": "axm.object-hinge-knuckle-owner-stack/v0.1",
    "contract_id": "modular-equipment-case-001-hinge-knuckle-owner-stack-001",
    "asset_id": "modular-equipment-case-001",
    "host_source_sha256": SOURCE_SHA256,
    "hinge_axis": [1, 0, 0],
    "ordered_knuckles": [
        {"id": "b0", "owner": "body"},
        {"id": "l0", "owner": "lid"},
        {"id": "b1", "owner": "body"},
        {"id": "l1", "owner": "lid"},
        {"id": "b2", "owner": "body"},
    ],
    "expected_owner_counts": {"body": 3, "lid": 2},
    "expected_knuckle_length_m": 0.1,
    "expected_center_pitch_m": 0.14,
    "expected_inter_knuckle_gap_m": 0.04,
    "minimum_source_axial_clearance_m": 0.01,
    "terminal_owner": "body",
    "required_lid_bracketing_owner": "body",
    "authority": {
        "source_geometry_changed": False,
        "rig_parenting_authorized": False,
        "animation_authorized": False,
        "physical_retention_claimed": False,
        "load_capacity_claimed": False,
        "manufacturing_fit_claimed": False,
    },
    "truth_boundary": "source owner-stack fixture",
}

LID_PLAN = {
    "schema": "axm.object-articulation-plan/v0.1",
    "asset_id": "modular-equipment-case-001",
    "source_sha256": SOURCE_SHA256,
    "joint": {
        "id": "rear-lid-hinge-001",
        "axis_source": "hinge.axis",
        "moving_component": "lid_shell",
        "fixed_component": "body_shell",
        "coaxial_moving_knuckles": ["l0", "l1"],
        "opening_rotation_sign": -1,
        "angle_limit_deg": [0, 110],
        "representative_angles_deg": [0, 30, 60, 90, 110],
        "sweep_step_deg": 1,
    },
    "assumptions": [
        "latches_disengaged_not_articulated",
        "rigid_body_and_lid_shells",
        "body_shell_separation_only_not_full_component_collision",
    ],
    "claim_scope": "bounded source-owned rigid lid articulation around the exact rear hinge; no animation performance, controller, runtime, gameplay or engineering acceptance",
}


class HingeKnuckleRigParentBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_path = ROOT / "assets/modular-equipment-case-001/source.json"
        self.source = json.loads(self.source_path.read_text(encoding="utf-8"))

    def run_verify(self, *, owner_stack=None, lid_plan=None, previous_head=PREVIOUS_RIGGING_HEAD):
        return verify(
            self.source,
            owner_stack or OWNER_STACK,
            lid_plan or LID_PLAN,
            source_sha256=sha256_file(self.source_path),
            observed_owner_stack_head=OWNER_STACK_HEAD,
            observed_owner_stack_blob=OWNER_STACK_BLOB,
            observed_lid_rig_head=LID_RIG_HEAD,
            observed_previous_rigging_head=previous_head,
        )

    def test_exact_owner_stack_matches_rig_parent_partition_and_continuous_axis_certificate(self):
        receipt = self.run_verify()
        self.assertEqual(receipt["result"], RESULT)
        self.assertEqual(receipt["rig_parent_partition"]["moving_lid_knuckles"], ["l0", "l1"])
        self.assertEqual(receipt["rig_parent_partition"]["fixed_body_knuckles"], ["b0", "b1", "b2"])
        self.assertEqual(receipt["continuous_certificate"]["domain_deg"], [0.0, 110.0])
        self.assertAlmostEqual(receipt["continuous_certificate"]["minimum_invariant_gap_m"], 0.04, places=12)
        self.assertAlmostEqual(receipt["continuous_certificate"]["minimum_clearance_surplus_m"], 0.03, places=12)
        self.assertLessEqual(receipt["metrics"]["max_axial_center_residual_m"], 1e-12)
        self.assertLessEqual(receipt["metrics"]["max_axial_interval_residual_m"], 1e-12)
        self.assertLessEqual(receipt["metrics"]["max_moving_radius_residual_m"], 1e-12)
        self.assertLessEqual(receipt["metrics"]["max_moving_inverse_recovery_residual_m"], 1e-12)
        self.assertEqual(receipt["metrics"]["max_fixed_body_knuckle_point_drift_m"], 0.0)
        self.assertFalse(receipt["truth_boundary"]["animation_accepted"])
        self.assertFalse(receipt["truth_boundary"]["runtime_accepted"])
        self.assertFalse(receipt["truth_boundary"]["technical_art_target_host_parenting_accepted"])

    def test_source_owner_label_drift_fails_closed(self):
        bad = copy.deepcopy(OWNER_STACK)
        bad["ordered_knuckles"][1]["owner"] = "body"
        with self.assertRaisesRegex(AssertionError, "source/owner-stack knuckle identity drift|moving-knuckle"):
            self.run_verify(owner_stack=bad)

    def test_body_owned_knuckle_in_moving_set_fails_closed(self):
        bad = copy.deepcopy(LID_PLAN)
        bad["joint"]["coaxial_moving_knuckles"] = ["l0", "b1", "l1"]
        with self.assertRaises(AssertionError):
            self.run_verify(lid_plan=bad)

    def test_lid_owned_knuckle_missing_from_moving_set_fails_closed(self):
        bad = copy.deepcopy(LID_PLAN)
        bad["joint"]["coaxial_moving_knuckles"] = ["l0"]
        with self.assertRaises(AssertionError):
            self.run_verify(lid_plan=bad)

    def test_source_owner_cannot_pre_authorize_rig_parenting(self):
        bad = copy.deepcopy(OWNER_STACK)
        bad["authority"]["rig_parenting_authorized"] = True
        with self.assertRaisesRegex(AssertionError, "source-owner authority drift"):
            self.run_verify(owner_stack=bad)

    def test_predecessor_rigging_identity_drift_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "previous Rigging head drift"):
            self.run_verify(previous_head="0" * 40)


if __name__ == "__main__":
    unittest.main()
