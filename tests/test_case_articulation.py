from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from case_articulation import inspect_articulation

ASSET = ROOT / "assets" / "modular-equipment-case-001"
SOURCE_PATH = ASSET / "source.json"
SOURCE = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
PLAN = json.loads((ASSET / "articulation.json").read_text(encoding="utf-8"))
SOURCE_SHA256 = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()


class CaseArticulationTests(unittest.TestCase):
    def test_exact_source_identity_and_determinism(self):
        self.assertEqual(SOURCE_SHA256, "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a")
        first = inspect_articulation(SOURCE, SOURCE_SHA256, PLAN)
        second = inspect_articulation(SOURCE, SOURCE_SHA256, PLAN)
        self.assertEqual(first, second)
        self.assertEqual(first["gate"], "PASS_SCOPED_LID_ARTICULATION")
        self.assertEqual(first["source_sha256"], SOURCE_SHA256)

    def test_exact_source_hinge_and_sampled_motion_boundary(self):
        report = inspect_articulation(SOURCE, SOURCE_SHA256, PLAN)
        self.assertEqual(report["hinge_axis"], [1.0, 0.0, 0.0])
        self.assertEqual(report["hinge_origin_m"], [0.0, 0.252, 0.306])
        self.assertEqual(report["coaxial_moving_knuckles"], ["l0", "l1"])
        self.assertEqual(report["angle_limit_deg"], [0.0, 110.0])
        self.assertEqual(report["sweep_step_deg"], 1)
        self.assertEqual(report["sweep_sample_count"], 111)
        self.assertEqual(report["sweep_minimum_separation_angle_deg"], 0.0)
        self.assertAlmostEqual(report["sweep_minimum_body_shell_separating_margin_m"], 0.012, places=12)
        self.assertLessEqual(report["sweep_maximum_lid_pairwise_rigidity_drift_m"], 1e-9)
        for sample in report["sweep_samples"]:
            self.assertEqual(sample["status"], "PASS")
            self.assertGreater(sample["body_shell_separating_margin_m"], 1e-9)
            self.assertLessEqual(sample["lid_pairwise_rigidity_max_drift_m"], 1e-9)
            self.assertEqual(sample["hinge_origin_drift_m"], 0.0)

    def test_representative_pose_receipt_is_exact(self):
        report = inspect_articulation(SOURCE, SOURCE_SHA256, PLAN)
        poses = {row["open_angle_deg"]: row for row in report["representative_poses"]}
        self.assertEqual(sorted(poses), [0.0, 30.0, 60.0, 90.0, 110.0])
        expected_margins = {
            0.0: 0.012,
            30.0: 0.017196152423,
            60.0: 0.019392304845,
            90.0: 0.018,
            110.0: 0.021742397445,
        }
        for angle, expected in expected_margins.items():
            self.assertAlmostEqual(poses[angle]["body_shell_separating_margin_m"], expected, places=12)
            self.assertEqual(poses[angle]["status"], "PASS")

    def test_wrong_source_identity_fails_closed(self):
        changed = copy.deepcopy(PLAN)
        changed["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source_sha256"):
            inspect_articulation(SOURCE, SOURCE_SHA256, changed)

    def test_unapproved_motion_envelope_fails_closed(self):
        changed = copy.deepcopy(PLAN)
        changed["joint"]["angle_limit_deg"] = [0, 120]
        with self.assertRaisesRegex(ValueError, "0..110"):
            inspect_articulation(SOURCE, SOURCE_SHA256, changed)

    def test_wrong_moving_hinge_identity_fails_closed(self):
        changed = copy.deepcopy(PLAN)
        changed["joint"]["coaxial_moving_knuckles"] = ["l0"]
        with self.assertRaisesRegex(ValueError, "coaxial_moving_knuckles"):
            inspect_articulation(SOURCE, SOURCE_SHA256, changed)


if __name__ == "__main__":
    unittest.main()
