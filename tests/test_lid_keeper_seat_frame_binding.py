from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_lid_keeper_seat_frame_binding import (  # noqa: E402
    KEEPER_SEAT_BLOB,
    KEEPER_SEAT_HEAD,
    LID_RIG_HEAD,
    PREVIOUS_RIGGING_HEAD,
    RESULT,
    SOURCE_SHA256,
    sha256_file,
    verify,
)

PLAN = {
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


def seat_fixture(ownership_sha256: str) -> dict:
    return {
        "schema": "axm.object-front-latch-keeper-seat/v0.1",
        "contract_id": "front-latch-keeper-seat-001",
        "asset_id": "modular-equipment-case-001",
        "host_source_sha256": SOURCE_SHA256,
        "ownership_contract_sha256": ownership_sha256,
        "purpose": "test fixture matching exact source-owner seat semantics",
        "stations": [
            {
                "id": "front-latch-left",
                "source_index": 0,
                "keeper_component": "latch_0_keeper",
                "owner_component": "lid_shell",
                "owner_face": "negative_y_face",
                "keeper_face": "positive_y_face",
                "plane_axis": "y",
                "plane_coordinate_m": -0.24,
                "owner_outward_normal": [0.0, -1.0, 0.0],
                "primary_axis": [1.0, 0.0, 0.0],
                "secondary_axis": [0.0, 0.0, 1.0],
                "primary_bounds_m": [-0.26, -0.18],
                "secondary_bounds_m": [0.312, 0.3335],
                "dimensions_m": [0.08, 0.0215],
                "area_m2": 0.00172,
                "center_m": [-0.22, -0.24, 0.32275],
            },
            {
                "id": "front-latch-right",
                "source_index": 1,
                "keeper_component": "latch_1_keeper",
                "owner_component": "lid_shell",
                "owner_face": "negative_y_face",
                "keeper_face": "positive_y_face",
                "plane_axis": "y",
                "plane_coordinate_m": -0.24,
                "owner_outward_normal": [0.0, -1.0, 0.0],
                "primary_axis": [1.0, 0.0, 0.0],
                "secondary_axis": [0.0, 0.0, 1.0],
                "primary_bounds_m": [0.18, 0.26],
                "secondary_bounds_m": [0.312, 0.3335],
                "dimensions_m": [0.08, 0.0215],
                "area_m2": 0.00172,
                "center_m": [0.22, -0.24, 0.32275],
            },
        ],
        "contact_policy": {
            "require_exact_face_contact": True,
            "require_zero_owner_volume_penetration": True,
            "require_positive_planar_overlap": True,
            "semantics": "static_source_attachment_reference_seat_only_not_retention_or_motion",
        },
        "authority": {
            "physical_fastener_or_weld_defined": False,
            "retention_force_defined": False,
            "manufacturing_tolerance_defined": False,
            "rig_motion_defined": False,
            "animation_timing_defined": False,
            "runtime_parenting_adopted": False,
        },
    }


class LidKeeperSeatFrameBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_path = ROOT / "assets/modular-equipment-case-001/source.json"
        self.ownership_path = ROOT / "assets/modular-equipment-case-001/front-latch-ownership-001.json"
        self.source = json.loads(self.source_path.read_text(encoding="utf-8"))
        self.ownership = json.loads(self.ownership_path.read_text(encoding="utf-8"))
        self.ownership_sha = sha256_file(self.ownership_path)
        self.seat = seat_fixture(self.ownership_sha)

    def run_verify(self, *, seat=None, override=None):
        return verify(
            self.source,
            self.ownership,
            seat or self.seat,
            PLAN,
            source_sha256=sha256_file(self.source_path),
            ownership_sha256=self.ownership_sha,
            observed_keeper_seat_head=KEEPER_SEAT_HEAD,
            observed_keeper_seat_blob=KEEPER_SEAT_BLOB,
            observed_lid_rig_head=LID_RIG_HEAD,
            observed_previous_rigging_head=PREVIOUS_RIGGING_HEAD,
            seat_override=override,
        )

    def test_exact_source_owned_seat_frames_bind_through_111_pose_field(self):
        receipt = self.run_verify()
        self.assertEqual(receipt["result"], RESULT)
        binding = receipt["seat_frame_binding"]
        self.assertEqual(binding["sweep_sample_count"], 111)
        self.assertEqual(binding["representative_angles_deg"], [0, 30, 50, 60, 90, 100, 110])
        self.assertLessEqual(binding["max_seat_center_recovery_residual_m"], 1e-12)
        self.assertLessEqual(binding["max_seat_axis_recovery_residual"], 1e-12)
        self.assertLessEqual(binding["max_seat_corner_recovery_residual_m"], 1e-12)
        self.assertLessEqual(binding["max_seat_pairwise_distance_drift_m"], 1e-12)
        self.assertLessEqual(binding["max_seat_area_drift_m2"], 1e-12)
        self.assertLessEqual(binding["max_lid_local_seat_offset_residual_m"], 1e-12)
        self.assertLessEqual(binding["max_keeper_local_seat_offset_residual_m"], 1e-12)
        self.assertFalse(receipt["truth_boundary"]["animation_accepted"])
        self.assertFalse(receipt["truth_boundary"]["runtime_accepted"])

    def test_one_millimeter_seat_center_drift_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "seat center"):
            self.run_verify(override={"front-latch-left": {"center_m": [-0.219, -0.24, 0.32275]}})

    def test_seat_axis_drift_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "primary axis"):
            self.run_verify(override={"front-latch-left": {"primary_axis": [0.0, 1.0, 0.0]}})

    def test_source_owner_authority_expansion_fails_closed(self):
        bad = copy.deepcopy(self.seat)
        bad["authority"]["runtime_parenting_adopted"] = True
        with self.assertRaisesRegex(AssertionError, "authority expansion forbidden"):
            self.run_verify(seat=bad)

    def test_source_owner_head_drift_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "keeper-seat source-owner head drift"):
            verify(
                self.source,
                self.ownership,
                self.seat,
                PLAN,
                source_sha256=sha256_file(self.source_path),
                ownership_sha256=self.ownership_sha,
                observed_keeper_seat_head="0" * 40,
                observed_keeper_seat_blob=KEEPER_SEAT_BLOB,
                observed_lid_rig_head=LID_RIG_HEAD,
                observed_previous_rigging_head=PREVIOUS_RIGGING_HEAD,
            )


if __name__ == "__main__":
    unittest.main()
