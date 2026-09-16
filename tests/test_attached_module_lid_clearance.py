from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from certify_attached_module_lid_clearance import RESULT, certify

ASSET = ROOT / "assets" / "modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
MODULE_PATH = ASSET / "utility-module-001.json"
CONSTRAINT_PATH = ASSET / "attached-module-lid-clearance.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
MODULE = json.loads(MODULE_PATH.read_text(encoding="utf-8"))
CONSTRAINT = json.loads(CONSTRAINT_PATH.read_text(encoding="utf-8"))
HOST_SHA = hashlib.sha256(HOST_PATH.read_bytes()).hexdigest()
MODULE_SHA = hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest()

# Exact rig-plan content from the pinned donor commit in CONSTRAINT. CI independently
# fetches the actual bytes from that commit and runs the certificate against them.
RIG_PLAN = {
    "schema": "axm.object-articulation-plan/v0.1",
    "asset_id": "modular-equipment-case-001",
    "source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
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


class AttachedModuleLidClearanceTests(unittest.TestCase):
    def test_exact_bilateral_attachment_receives_continuous_certificate(self):
        report = certify(HOST, HOST_SHA, MODULE, MODULE_SHA, RIG_PLAN, CONSTRAINT)
        self.assertEqual(report["result"], RESULT)
        self.assertEqual(report["host_source_sha256"], HOST_SHA)
        self.assertEqual(report["module_source_sha256"], MODULE_SHA)
        self.assertEqual(report["rig_plan_digest"], CONSTRAINT["rig_donor"]["plan_digest"])
        self.assertEqual(report["angle_limit_deg"], [0.0, 110.0])
        self.assertEqual(report["hinge_axis"], [1, 0, 0])
        self.assertAlmostEqual(report["continuous_minimum_lid_to_module_clearance_m"], 0.03, places=12)
        self.assertEqual(report["simultaneous_bilateral_attachment_status"], "PASS")

    def test_representative_poses_preserve_same_invariant_clearance(self):
        report = certify(HOST, HOST_SHA, MODULE, MODULE_SHA, RIG_PLAN, CONSTRAINT)
        self.assertEqual([row["open_angle_deg"] for row in report["representative_poses"]], [0.0, 30.0, 60.0, 90.0, 110.0])
        for pose in report["representative_poses"]:
            self.assertEqual(pose["lid_x_interval_m"], [-0.39, 0.39])
            self.assertEqual(pose["status"], "PASS")
            self.assertAlmostEqual(pose["socket_clearance_m"]["left-service-socket"], 0.03, places=12)
            self.assertAlmostEqual(pose["socket_clearance_m"]["right-service-socket"], 0.03, places=12)

    def test_world_intervals_are_bilateral_and_source_frame_bound(self):
        report = certify(HOST, HOST_SHA, MODULE, MODULE_SHA, RIG_PLAN, CONSTRAINT)
        rows = {row["socket_id"]: row for row in report["socket_results"]}
        self.assertEqual(rows["left-service-socket"]["module_x_interval_m"], [-0.515, -0.42])
        self.assertEqual(rows["right-service-socket"]["module_x_interval_m"], [0.42, 0.515])
        self.assertEqual(rows["left-service-socket"]["normal"], [-1, 0, 0])
        self.assertEqual(rows["right-service-socket"]["normal"], [1, 0, 0])

    def test_wrong_rig_envelope_fails_closed(self):
        bad = copy.deepcopy(RIG_PLAN)
        bad["joint"]["angle_limit_deg"] = [0, 120]
        with self.assertRaisesRegex(ValueError, "rig donor plan digest|rig motion envelope"):
            certify(HOST, HOST_SHA, MODULE, MODULE_SHA, bad, CONSTRAINT)

    def test_non_x_hinge_fails_closed(self):
        bad_host = copy.deepcopy(HOST)
        bad_host["hinge"]["axis"] = [0, 0, 1]
        with self.assertRaisesRegex(ValueError, "requires exact \\+X hinge axis"):
            certify(bad_host, HOST_SHA, MODULE, MODULE_SHA, RIG_PLAN, CONSTRAINT)

    def test_zero_standoff_rejects_touching_module(self):
        bad_module = copy.deepcopy(MODULE)
        bad_module["interface"]["standoff_from_socket_origin_m"] = 0.0
        with self.assertRaisesRegex(ValueError, "does not stay positively separated"):
            certify(HOST, HOST_SHA, bad_module, MODULE_SHA, RIG_PLAN, CONSTRAINT)


if __name__ == "__main__":
    unittest.main()
