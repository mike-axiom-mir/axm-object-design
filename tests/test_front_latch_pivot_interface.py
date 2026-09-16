import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_front_latch_pivot_interface as pivot

ASSET = ROOT / "assets/modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
OWNERSHIP_PATH = ASSET / "front-latch-ownership-001.json"
INTERFACE_PATH = ASSET / "front-latch-pivot-interface-001.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
OWNERSHIP = json.loads(OWNERSHIP_PATH.read_text(encoding="utf-8"))
INTERFACE = json.loads(INTERFACE_PATH.read_text(encoding="utf-8"))
RIGGING_PLAN_SHA = "81c27ab7b73ed9a43cb3f554b56c3f4294b893712075e33d13f5b02e008455db"
RIGGING_PLAN = {
    "host_source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
    "ownership_donor_head": "d3fa10a270faae7925811f44f03381fe5c5d0215",
    "pivot_rule": "source_x__panel_negative_y_face__lever_min_z",
    "joint_axis": [1.0, 0.0, 0.0],
    "review_angle_min_deg": 0.0,
    "review_angle_max_deg": 50.0,
}


class FrontLatchPivotInterfaceTests(unittest.TestCase):
    def verify(self, interface=INTERFACE, rigging_plan=RIGGING_PLAN, rigging_plan_sha=RIGGING_PLAN_SHA):
        return pivot.verify(
            HOST,
            OWNERSHIP,
            interface,
            rigging_plan,
            host_sha=pivot.sha256(HOST_PATH),
            ownership_sha=pivot.sha256(OWNERSHIP_PATH),
            interface_sha=pivot.sha256(INTERFACE_PATH),
            rigging_plan_sha=rigging_plan_sha,
        )

    def test_exact_source_owns_reviewed_bilateral_pivot_interface(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_FRONT_LATCH_PIVOT_INTERFACE")
        self.assertEqual(receipt["station_count"], 2)
        self.assertFalse(receipt["host_geometry_changed"])
        self.assertEqual(receipt["joint_axis"], [1.0, 0.0, 0.0])
        self.assertAlmostEqual(receipt["maximum_pivot_rule_residual_m"], 0.0)
        self.assertAlmostEqual(receipt["bilateral_pivot_residual_m"], 0.0)
        self.assertAlmostEqual(receipt["bilateral_release_threshold_residual_deg"], 0.0)
        self.assertAlmostEqual(receipt["terminal_keeper_z_separation_m"], 0.0015728659779458698, places=12)
        self.assertAlmostEqual(receipt["release_threshold_deg"], 48.66480246428277, places=10)
        for row in receipt["station_results"]:
            self.assertGreater(min(row["closed_keeper_lever_overlap_m"].values()), 0.0)
            self.assertGreaterEqual(row["terminal_keeper_z_separation_m"], 0.001)

    def test_rejects_pivot_origin_drift_from_source_rule(self):
        bad = copy.deepcopy(INTERFACE)
        bad["stations"][0]["pivot_origin_m"][1] += 0.001
        with self.assertRaisesRegex(AssertionError, "pivot origin drift"):
            self.verify(interface=bad)

    def test_rejects_ownership_component_drift(self):
        bad = copy.deepcopy(INTERFACE)
        bad["stations"][0]["keeper_owner_component"] = "body_shell"
        with self.assertRaisesRegex(AssertionError, "ownership/component drift"):
            self.verify(interface=bad)

    def test_rejects_release_requirement_beyond_exact_review_endpoint(self):
        bad = copy.deepcopy(INTERFACE)
        bad["travel_envelope_deg"]["minimum_release_separation_m"] = 0.01
        with self.assertRaisesRegex(AssertionError, "release separation"):
            self.verify(interface=bad)

    def test_rejects_rigging_donor_identity_drift(self):
        with self.assertRaisesRegex(AssertionError, "Rigging donor plan identity mismatch"):
            self.verify(rigging_plan_sha="0" * 64)


if __name__ == "__main__":
    unittest.main()
