from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from certify_registration_key_lid_clearance import RESULT, certify

ASSET = ROOT / "assets" / "modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
MODULE_PATH = ASSET / "utility-module-001.json"
BASE_CONSTRAINT_PATH = ASSET / "attached-module-lid-clearance.json"
CONSTRAINT_PATH = ASSET / "registration-key-lid-clearance.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
MODULE = json.loads(MODULE_PATH.read_text(encoding="utf-8"))
BASE_CONSTRAINT = json.loads(BASE_CONSTRAINT_PATH.read_text(encoding="utf-8"))
CONSTRAINT = json.loads(CONSTRAINT_PATH.read_text(encoding="utf-8"))
HOST_SHA = hashlib.sha256(HOST_PATH.read_bytes()).hexdigest()
MODULE_SHA = hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest()

# Exact plan content pinned by the existing Rigging constraint. The retained-evidence
# workflow separately materializes these bytes from the exact donor commit.
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

# Exact JSON semantics from Hard-Surface PR #9 head 3f091bda... . Unit tests use
# this in-memory copy; CI additionally fetches the source bytes from that exact commit.
REGISTRATION = {
    "schema": "axm.object-service-module-registration-key/v0.1",
    "asset_id": "utility-module-registration-key-001",
    "host_asset_id": "modular-equipment-case-001",
    "module_asset_id": "utility-module-001",
    "units": "meters",
    "intent": "bounded source-owned asymmetric registration datum overlay for the existing service-module interface; breaks the physically ambiguous 180-degree orientation of the symmetric four-point mount pattern without rewriting the proven host or module sources",
    "source_identity": {
        "host_source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
        "module_source_sha256": "ffd7b42294d3af71e02aa172157beccefa08c6af2c1198f88836862d2a50fc2e",
        "hard_surface_prerequisite_head": "9a0524319cc3fe33bdbb2d76505b2c89a7a9f190",
    },
    "datum": {
        "position_local_lateral_up_m": [0.027, 0.014],
        "host_pin_radius_m": 0.0025,
        "host_pin_projection_m": 0.004,
        "module_recess_radius_m": 0.003,
        "module_recess_depth_m": 0.006,
        "minimum_edge_margin_m": 0.005,
        "maximum_center_residual_m": 0.0005,
    },
    "orientation_contract": "The module keeps the existing source-frame convention. In the seated orientation the module registration recess is at the same local lateral/up coordinate as the host pin. A 180-degree in-plane rotation must not remain capturable by this datum.",
    "provenance": {
        "method": "AXM self-authored deterministic hard-surface registration candidate",
        "external_assets": [],
        "external_geometry": False,
    },
    "truth_boundary": "This overlay proves only a bounded asymmetric physical registration datum against the exact existing host/module interface geometry. It does not prove fastener retention, engineering load, vibration, tolerance stack, wear, waterproofing, runtime attachment, physics, gameplay, final topology/materials, Art Direction acceptance, CANON or production readiness.",
}


class RegistrationKeyLidClearanceTests(unittest.TestCase):
    def run_certificate(self, registration=None, constraint=None):
        return certify(
            HOST,
            HOST_SHA,
            MODULE,
            MODULE_SHA,
            RIG_PLAN,
            BASE_CONSTRAINT,
            REGISTRATION if registration is None else registration,
            "unit-test-registration-source",
            CONSTRAINT if constraint is None else constraint,
        )

    def test_exact_registered_bilateral_attachment_passes(self):
        report = self.run_certificate()
        self.assertEqual(report["result"], RESULT)
        self.assertEqual(report["base_clearance_result"], "PASS_CONTINUOUS_LID_TO_BILATERAL_SERVICE_MODULE_CLEARANCE")
        self.assertAlmostEqual(report["module_body_continuous_clearance_m"], 0.03, places=12)
        self.assertAlmostEqual(report["registration_pin_continuous_clearance_m"], 0.012, places=12)
        self.assertAlmostEqual(report["continuous_minimum_lid_to_registered_attachment_clearance_m"], 0.012, places=12)

    def test_exact_pin_intervals_are_bilateral_and_reduce_clearance(self):
        report = self.run_certificate()
        rows = {row["socket_id"]: row for row in report["registration_key_results"]}
        self.assertEqual(rows["left-service-socket"]["pin_x_interval_m"], [-0.406, -0.402])
        self.assertEqual(rows["right-service-socket"]["pin_x_interval_m"], [0.402, 0.406])
        for row in rows.values():
            self.assertAlmostEqual(row["continuous_lid_to_pin_clearance_m"], 0.012, places=12)

    def test_representative_poses_preserve_continuous_bound(self):
        report = self.run_certificate()
        self.assertEqual(
            [pose["open_angle_deg"] for pose in report["representative_poses"]],
            [0.0, 30.0, 60.0, 90.0, 110.0],
        )
        for pose in report["representative_poses"]:
            self.assertEqual(pose["lid_x_interval_m"], [-0.39, 0.39])
            self.assertAlmostEqual(pose["minimum_module_body_clearance_m"], 0.03, places=12)
            self.assertAlmostEqual(pose["minimum_registration_pin_clearance_m"], 0.012, places=12)
            self.assertAlmostEqual(pose["minimum_registered_attachment_clearance_m"], 0.012, places=12)
            self.assertEqual(pose["status"], "PASS")

    def test_wrong_registration_source_identity_fails_closed(self):
        bad = copy.deepcopy(REGISTRATION)
        bad["source_identity"]["host_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "registration host source identity mismatch"):
            self.run_certificate(registration=bad)

    def test_wrong_registration_donor_commit_fails_closed(self):
        bad = copy.deepcopy(CONSTRAINT)
        bad["registration_donor"]["commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "registration donor commit mismatch"):
            self.run_certificate(constraint=bad)

    def test_nonpositive_pin_projection_fails_closed(self):
        bad = copy.deepcopy(REGISTRATION)
        bad["datum"]["host_pin_projection_m"] = 0.0
        with self.assertRaisesRegex(ValueError, "registration host pin dimensions must be positive"):
            self.run_certificate(registration=bad)


if __name__ == "__main__":
    unittest.main()
