from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_hinge_bored_knuckle_rig_compatibility import (  # noqa: E402
    ANNULAR_BLOB,
    LID_RIG_HEAD,
    MOTION_CLEARANCE_GATE,
    OWNER_STACK_BLOB,
    PREDECESSOR_RIGGING_HEAD,
    RESULT,
    SUCCESSOR_BLOB,
    SUCCESSOR_HEAD,
    sha256_file,
    verify,
)
from verify_hinge_knuckle_rig_parent_binding import OWNER_STACK_HEAD, SOURCE_SHA256  # noqa: E402


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

SUCCESSOR = {
    "schema": "axm.object-hinge-bored-knuckle-source-successor/v0.1",
    "asset_id": "modular-equipment-case-001",
    "successor_id": "modular-equipment-case-001/hinge-bored-knuckle-source-successor-001",
    "units": "meters",
    "legacy_host_source_sha256": SOURCE_SHA256,
    "annular_mesh_contract_git_blob_sha1": ANNULAR_BLOB,
    "bore_clearance_contract_git_blob_sha1": "e94fbc0d960d949f49fc3a05edba74b706f2a87e",
    "owner_stack_contract_git_blob_sha1": OWNER_STACK_BLOB,
    "successor_semantics": "SOURCE_OWNED_ALTERNATE_HINGE_KNUCKLE_GEOMETRY_EXPLICIT_RECEIVER_REBIND_REQUIRED",
    "replacement_scope": "HINGE_KNUCKLE_GEOMETRY_ONLY",
    "source_owned_successor": {
        "knuckle_geometry": "exact faceting-aware annular mesh defined by hinge-pin-annular-mesh-001.json",
        "pin_geometry": "legacy source pin retained unchanged",
        "minimum_pin_to_bore_surface_clearance_m": 0.001,
        "automatic_default_replacement": False,
        "automatic_downstream_adoption": False,
        "legacy_host_source_rewritten": False,
    },
    "authority": {
        "hard_surface_source_successor_authorized": True,
        "rig_parenting_authorized": False,
        "animation_authorized": False,
        "runtime_or_physics_authorized": False,
        "manufacturing_fit_class_authorized": False,
        "load_strength_wear_authorized": False,
        "visual_acceptance_authorized": False,
        "uc_or_profession_fabric_promotion_authorized": False,
    },
}

ANNULAR = {
    "schema": "axm.object-hinge-pin-annular-mesh/v0.1",
    "asset_id": "modular-equipment-case-001",
    "units": "meters",
    "host_source_sha256": SOURCE_SHA256,
    "bore_clearance_contract_sha256": "4dacff22053c39fcd037cdb568480dafdf78e52b18b9994965f1c396b344f4d7",
    "expected_knuckle_count": 5,
    "expected_segments": 12,
    "source_pin_radius_m": 0.009,
    "analytic_review_bore_radius_m": 0.010,
    "mesh_bore_radius_m": 0.010035276180410082,
    "minimum_mesh_surface_clearance_m": 0.001,
    "minimum_mesh_knuckle_wall_m": 0.010,
    "faceting_policy": "SAME_PHASE_REGULAR_N_GON_CIRCUMRADIUS_COMPENSATION_FOR_MINIMUM_SURFACE_GAP",
    "candidate_semantics": "DERIVED_ANNULAR_KNUCKLE_REVIEW_MESH_NOT_ADOPTED_HOST_GEOMETRY",
}

SUCCESSOR_RECEIPT = {
    "schema": "axm.object-hinge-bored-knuckle-source-successor-receipt/v0.1",
    "result": "PASS_SOURCE_OWNED_BORED_HINGE_KNUCKLE_SUCCESSOR",
    "asset_id": "modular-equipment-case-001",
    "successor_id": "modular-equipment-case-001/hinge-bored-knuckle-source-successor-001",
    "annular_mesh_contract_git_blob_sha1": ANNULAR_BLOB,
    "bore_clearance_contract_git_blob_sha1": "e94fbc0d960d949f49fc3a05edba74b706f2a87e",
    "owner_stack_contract_git_blob_sha1": OWNER_STACK_BLOB,
    "minimum_pin_to_bore_surface_clearance_m": 0.001,
    "automatic_downstream_adoption": False,
}


class BoredKnuckleRigCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_path = ROOT / "assets/modular-equipment-case-001/source.json"
        self.source = json.loads(self.source_path.read_text(encoding="utf-8"))
        self.compatibility = json.loads(
            (ROOT / "assets/modular-equipment-case-001/hinge-bored-knuckle-rig-compatibility-001.json").read_text(
                encoding="utf-8"
            )
        )

    def run_verify(self, *, successor=None, annular=None, compatibility=None, predecessor=PREDECESSOR_RIGGING_HEAD):
        return verify(
            self.source,
            OWNER_STACK,
            successor or SUCCESSOR,
            annular or ANNULAR,
            SUCCESSOR_RECEIPT,
            LID_PLAN,
            compatibility or self.compatibility,
            source_sha256=sha256_file(self.source_path),
            observed_owner_stack_head=OWNER_STACK_HEAD,
            observed_owner_stack_blob=OWNER_STACK_BLOB,
            observed_successor_head=SUCCESSOR_HEAD,
            observed_successor_blob=SUCCESSOR_BLOB,
            observed_annular_blob=ANNULAR_BLOB,
            observed_lid_rig_head=LID_RIG_HEAD,
            observed_predecessor_rigging_head=predecessor,
        )

    def test_phase_independent_positive_clearance_is_continuous_and_bounded(self):
        receipt = self.run_verify()
        self.assertEqual(receipt["result"], RESULT)
        self.assertEqual(receipt["motion_clearance_gate"], MOTION_CLEARANCE_GATE)
        cert = receipt["continuous_radial_certificate"]
        self.assertEqual(cert["domain_deg"], [0.0, 110.0])
        self.assertAlmostEqual(cert["neutral_same_phase_clearance_m"], 0.001, places=12)
        self.assertAlmostEqual(
            cert["phase_independent_radial_clearance_lower_bound_m"],
            0.0006933324366016139,
            places=15,
        )
        self.assertAlmostEqual(
            cert["static_to_phase_independent_guarantee_drop_m"],
            0.0003066675633983861,
            places=15,
        )
        self.assertEqual(len(receipt["representative_pose_witnesses"]), 9)
        self.assertTrue(receipt["decision"]["continuous_positive_radial_clearance_proven"])
        self.assertFalse(receipt["decision"]["source_successor_geometry_adopted"])
        self.assertFalse(receipt["decision"]["source_static_1mm_promoted_to_continuous_motion_clearance"])
        self.assertFalse(receipt["truth_boundary"]["pin_parent_or_axial_phase_claimed"])
        self.assertFalse(receipt["truth_boundary"]["animation_accepted"])
        self.assertFalse(receipt["truth_boundary"]["runtime_accepted"])

    def test_automatic_successor_adoption_fails_closed(self):
        bad = copy.deepcopy(SUCCESSOR)
        bad["source_owned_successor"]["automatic_downstream_adoption"] = True
        with self.assertRaisesRegex(AssertionError, "automatic_downstream_adoption"):
            self.run_verify(successor=bad)

    def test_silent_pin_phase_claim_fails_closed(self):
        bad = copy.deepcopy(self.compatibility)
        bad["rig_constraint"]["pin_axial_phase"] = "FIXED_TO_BODY"
        with self.assertRaisesRegex(AssertionError, "pin axial phase"):
            self.run_verify(compatibility=bad)

    def test_bore_geometry_drift_fails_closed(self):
        bad = copy.deepcopy(ANNULAR)
        bad["mesh_bore_radius_m"] = 0.0092
        with self.assertRaises(AssertionError):
            self.run_verify(annular=bad)

    def test_predecessor_rigging_identity_drift_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "predecessor Rigging head"):
            self.run_verify(predecessor="0" * 40)


if __name__ == "__main__":
    unittest.main()
