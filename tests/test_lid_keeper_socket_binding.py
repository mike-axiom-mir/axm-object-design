from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_lid_keeper_socket_binding import (  # noqa: E402
    LID_RIG_HEAD,
    OWNERSHIP_HEAD,
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


class LidKeeperSocketBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_path = ROOT / "assets/modular-equipment-case-001/source.json"
        self.ownership_path = ROOT / "assets/modular-equipment-case-001/front-latch-ownership-001.json"
        self.source = json.loads(self.source_path.read_text(encoding="utf-8"))
        self.ownership = json.loads(self.ownership_path.read_text(encoding="utf-8"))

    def run_verify(self, *, ownership=None, override=None):
        return verify(
            self.source,
            ownership or self.ownership,
            PLAN,
            source_sha256=sha256_file(self.source_path),
            observed_ownership_head=OWNERSHIP_HEAD,
            observed_lid_rig_head=LID_RIG_HEAD,
            observed_previous_rigging_head=PREVIOUS_RIGGING_HEAD,
            local_offset_override=override,
        )

    def test_exact_socket_binding_passes_111_pose_field(self):
        receipt = self.run_verify()
        self.assertEqual(receipt["result"], RESULT)
        self.assertEqual(receipt["socket_binding"]["sweep_sample_count"], 111)
        self.assertEqual(receipt["socket_binding"]["representative_angles_deg"], [0, 30, 50, 60, 90, 100, 110])
        self.assertLessEqual(receipt["socket_binding"]["max_lid_local_offset_residual_m"], 1e-12)
        self.assertLessEqual(receipt["socket_binding"]["max_keeper_rigidity_drift_m"], 1e-12)
        self.assertEqual(receipt["socket_binding"]["max_fixed_lever_center_drift_m"], 0.0)
        self.assertFalse(receipt["truth_boundary"]["animation_accepted"])
        self.assertFalse(receipt["truth_boundary"]["runtime_accepted"])

    def test_keeper_owner_drift_fails_closed(self):
        bad = copy.deepcopy(self.ownership)
        bad["stations"][0]["keeper_owner_component"] = "front_service_panel"
        with self.assertRaisesRegex(AssertionError, "keeper owner drift"):
            self.run_verify(ownership=bad)

    def test_one_millimeter_socket_offset_drift_fails_closed(self):
        # Exact neutral lid-local center offset is [-0.22, -0.251, -0.061] m.
        # A +1 mm X mutation must not be silently accepted as the same socket.
        override = {"latch_0_keeper": [-0.219, -0.251, -0.061]}
        with self.assertRaisesRegex(AssertionError, "keeper local socket offset drift"):
            self.run_verify(override=override)

    def test_donor_head_drift_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "lid articulation donor head drift"):
            verify(
                self.source,
                self.ownership,
                PLAN,
                source_sha256=sha256_file(self.source_path),
                observed_ownership_head=OWNERSHIP_HEAD,
                observed_lid_rig_head="0" * 40,
                observed_previous_rigging_head=PREVIOUS_RIGGING_HEAD,
            )


if __name__ == "__main__":
    unittest.main()
