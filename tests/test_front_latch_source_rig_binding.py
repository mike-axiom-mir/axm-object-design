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
BINDING_PATH = ASSET / "front-latch-source-rig-binding-002.json"
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


class FrontLatchSourceRigBindingTests(unittest.TestCase):
    def verify(self, binding=BINDING, interface=INTERFACE, interface_sha=None, historical_plan=HISTORICAL_PLAN):
        return rig.verify(
            HOST,
            OWNERSHIP,
            interface,
            historical_plan,
            binding,
            host_sha=rig.sha256(HOST_PATH),
            ownership_sha=rig.sha256(OWNERSHIP_PATH),
            interface_sha=interface_sha or rig.sha256(INTERFACE_PATH),
            historical_plan_sha=rig.EXPECTED_HISTORICAL_PLAN_SHA256,
            binding_sha=rig.sha256(BINDING_PATH),
        )

    def test_exact_source_owned_interface_rebinds_rigging_boundary(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_FRONT_LATCH_RIG_REBIND")
        self.assertEqual(receipt["rig_authority"], "CURRENT_SOURCE_INTERFACE_AUTHORITY")
        self.assertEqual(receipt["historical_rigging_role"], "PROVENANCE_ONLY_NOT_CURRENT_INTERFACE_AUTHORITY")
        self.assertEqual(receipt["pose_samples_deg"], [0.0, 25.0, 50.0])
        self.assertFalse(receipt["host_geometry_changed"])
        self.assertLessEqual(receipt["maximum_rigid_pairwise_distance_drift_m"], 1e-12)
        self.assertLessEqual(receipt["maximum_pivot_drift_m"], 1e-12)
        self.assertAlmostEqual(receipt["continuous_release_threshold_deg"], 48.66480246428277, places=10)
        self.assertAlmostEqual(receipt["minimum_midpoint_keeper_z_overlap_m"], 0.021057567601, places=9)
        self.assertAlmostEqual(receipt["minimum_endpoint_keeper_z_separation_m"], 0.0015728659779458698, places=12)
        self.assertAlmostEqual(receipt["bilateral_midpoint_overlap_residual_m"], 0.0, places=12)
        self.assertAlmostEqual(receipt["bilateral_endpoint_separation_residual_m"], 0.0, places=12)

    def test_rejects_source_interface_head_drift(self):
        bad = copy.deepcopy(BINDING)
        bad["source_interface"]["head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "source interface head drift"):
            self.verify(binding=bad)

    def test_rejects_source_interface_file_identity_drift(self):
        with self.assertRaisesRegex(AssertionError, "source interface file identity drift"):
            self.verify(interface_sha="0" * 64)

    def test_rejects_historical_plan_repromotion(self):
        bad = copy.deepcopy(BINDING)
        bad["historical_rigging_observation"]["role"] = "CURRENT_INTERFACE_AUTHORITY"
        with self.assertRaisesRegex(AssertionError, "historical Rigging role drift"):
            self.verify(binding=bad)

    def test_rejects_source_owned_pivot_drift(self):
        bad = copy.deepcopy(INTERFACE)
        bad["stations"][0]["pivot_origin_m"][2] += 0.001
        with self.assertRaisesRegex(AssertionError, "pivot origin drift from source rule"):
            self.verify(interface=bad, interface_sha=rig.EXPECTED_INTERFACE_SHA256)


if __name__ == "__main__":
    unittest.main()
