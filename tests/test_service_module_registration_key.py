import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_service_module_registration_key as r

HOST_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
MODULE_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-001.json"
REG_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-registration-key-001.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
MODULE = json.loads(MODULE_PATH.read_text(encoding="utf-8"))
REG = json.loads(REG_PATH.read_text(encoding="utf-8"))


class ServiceModuleRegistrationKeyTests(unittest.TestCase):
    def test_asymmetric_registration_passes(self):
        receipt = r.verify(
            HOST,
            MODULE,
            REG,
            host_sha=r.sha256(HOST_PATH),
            module_sha=r.sha256(MODULE_PATH),
        )
        self.assertEqual(receipt["result"], "PASS_ASYMMETRIC_REGISTRATION_KEY_PROOF")
        self.assertEqual(receipt["base_fit_result"], "PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF")
        self.assertEqual(receipt["base_mount_pattern_180_symmetry_residual_m"], 0.0)
        self.assertEqual(receipt["registration_orientation_residuals_m"]["0"], 0.0)
        self.assertGreater(receipt["registration_orientation_residuals_m"]["180"], 0.05)
        self.assertGreater(receipt["radial_clearance_m"], 0.0)
        self.assertGreater(receipt["axial_clearance_m"], 0.0)
        self.assertEqual(len(receipt["socket_results"]), 2)

    def test_rejects_centered_datum_that_preserves_180_ambiguity(self):
        bad = copy.deepcopy(REG)
        bad["datum"]["position_local_lateral_up_m"] = [0.0, 0.0]
        with self.assertRaisesRegex(AssertionError, "does not reject 180-degree rotation"):
            r.verify(HOST, MODULE, bad)

    def test_rejects_edge_margin_violation(self):
        bad = copy.deepcopy(REG)
        bad["datum"]["position_local_lateral_up_m"] = [0.052, 0.014]
        with self.assertRaisesRegex(AssertionError, "footprint edge margin"):
            r.verify(HOST, MODULE, bad)

    def test_rejects_insufficient_radial_clearance(self):
        bad = copy.deepcopy(REG)
        bad["datum"]["module_recess_radius_m"] = 0.0027
        with self.assertRaisesRegex(AssertionError, "radial clearance"):
            r.verify(HOST, MODULE, bad)

    def test_rejects_wrong_source_identity(self):
        with self.assertRaisesRegex(AssertionError, "host source identity mismatch"):
            r.verify(HOST, MODULE, REG, host_sha="0" * 64, module_sha=r.sha256(MODULE_PATH))


if __name__ == "__main__":
    unittest.main()
