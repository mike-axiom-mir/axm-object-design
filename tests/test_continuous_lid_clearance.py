from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from continuous_lid_clearance import RESULT, certify_continuous_shell_clearance

ASSET = ROOT / "assets" / "modular-equipment-case-001"
SOURCE_PATH = ASSET / "source.json"
SOURCE = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
PLAN = json.loads((ASSET / "articulation.json").read_text(encoding="utf-8"))
SOURCE_SHA256 = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()


class ContinuousLidClearanceTests(unittest.TestCase):
    def test_exact_source_receives_continuous_shell_certificate(self):
        report = certify_continuous_shell_clearance(SOURCE, SOURCE_SHA256, PLAN)
        self.assertEqual(report["result"], RESULT)
        self.assertEqual(report["source_sha256"], SOURCE_SHA256)
        self.assertEqual(report["angle_limit_deg"], [0.0, 110.0])
        self.assertEqual(report["certificate_method"], "piecewise_analytic_separating_axis")
        self.assertAlmostEqual(report["continuous_certified_minimum_separation_m"], 0.012, places=12)
        self.assertEqual(len(report["intervals"]), 2)
        self.assertEqual(report["intervals"][0]["open_angle_interval_deg"], [0.0, 90.0])
        self.assertEqual(report["intervals"][0]["separating_axis"], "global_z")
        self.assertEqual(report["intervals"][1]["open_angle_interval_deg"], [90.0, 110.0])
        self.assertEqual(report["intervals"][1]["separating_axis"], "global_y")
        self.assertTrue(report["sampled_sat_crosscheck"]["all_samples_pass"])
        self.assertEqual(report["sampled_sat_crosscheck"]["sample_count"], 111)

    def test_certificate_is_deterministic(self):
        first = certify_continuous_shell_clearance(SOURCE, SOURCE_SHA256, PLAN)
        second = certify_continuous_shell_clearance(SOURCE, SOURCE_SHA256, PLAN)
        self.assertEqual(first, second)

    def test_unsupported_hinge_geometry_fails_closed(self):
        source = copy.deepcopy(SOURCE)
        source["hinge"]["offset_z"] = source["dimensions_m"]["split_gap"] + 0.001
        changed_plan = copy.deepcopy(PLAN)
        synthetic_sha = "a" * 64
        changed_plan["source_sha256"] = synthetic_sha
        with self.assertRaisesRegex(ValueError, "0 <= hinge.offset_z <= split_gap"):
            certify_continuous_shell_clearance(source, synthetic_sha, changed_plan)


if __name__ == "__main__":
    unittest.main()
