import copy
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_service_module_fastener_clearance as f

HOST_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
MODULE_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-001.json"
REG_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-registration-key-001.json"
CLEARANCE_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-fastener-clearance-001.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
MODULE = json.loads(MODULE_PATH.read_text(encoding="utf-8"))
REG = json.loads(REG_PATH.read_text(encoding="utf-8"))
CLEARANCE = json.loads(CLEARANCE_PATH.read_text(encoding="utf-8"))


class ServiceModuleFastenerClearanceTests(unittest.TestCase):
    def verify(self, host=HOST, module=MODULE, registration=REG, clearance=CLEARANCE):
        return f.verify(
            host,
            module,
            registration,
            clearance,
            host_sha=f.sha256(HOST_PATH),
            module_sha=f.sha256(MODULE_PATH),
            registration_sha=f.sha256(REG_PATH),
        )

    def test_registration_preserves_reserved_fastener_axis_clearance(self):
        receipt = self.verify()
        self.assertEqual(
            receipt["result"],
            "PASS_REGISTRATION_KEY_PRESERVES_FASTENER_AXIS_CLEARANCE",
        )
        self.assertEqual(
            receipt["registration_prerequisite_result"],
            "PASS_ASYMMETRIC_REGISTRATION_KEY_PROOF",
        )
        self.assertAlmostEqual(receipt["reserved_fastener_axis_radius_m"], 0.01)
        self.assertAlmostEqual(
            receipt["minimum_fastener_to_fastener_surface_clearance_m"],
            0.03,
        )
        self.assertAlmostEqual(
            receipt["minimum_fastener_to_host_footprint_edge_margin_m"],
            0.01,
        )
        self.assertAlmostEqual(
            receipt["minimum_fastener_to_module_footprint_edge_margin_m"],
            0.004,
        )
        expected_recess_clearance = math.hypot(0.038 - 0.027, 0.025 - 0.014) - 0.01 - 0.003
        self.assertAlmostEqual(
            receipt["minimum_fastener_to_registration_recess_surface_clearance_m"],
            expected_recess_clearance,
        )
        self.assertGreater(
            receipt["minimum_fastener_to_registration_pin_surface_clearance_m"],
            receipt["minimum_fastener_to_registration_recess_surface_clearance_m"],
        )
        self.assertEqual(len(receipt["socket_results"]), 2)
        for socket in receipt["socket_results"]:
            self.assertLessEqual(socket["local_world_distance_residual_m"], 1e-9)

    def test_rejects_registration_datum_that_consumes_fastener_clearance(self):
        bad = copy.deepcopy(REG)
        bad["datum"]["position_local_lateral_up_m"] = [0.033, 0.020]
        with self.assertRaisesRegex(AssertionError, "registration .* consumes reserved fastener-axis clearance"):
            self.verify(registration=bad)

    def test_rejects_clearance_radius_that_breaks_module_footprint(self):
        bad = copy.deepcopy(MODULE)
        bad["interface"]["bolt_axis_clearance_radius_m"] = 0.0141
        with self.assertRaisesRegex(AssertionError, "exceeds module footprint"):
            self.verify(module=bad)

    def test_rejects_wrong_registration_source_identity(self):
        with self.assertRaisesRegex(AssertionError, "registration source identity mismatch"):
            f.verify(
                HOST,
                MODULE,
                REG,
                CLEARANCE,
                host_sha=f.sha256(HOST_PATH),
                module_sha=f.sha256(MODULE_PATH),
                registration_sha="0" * 64,
            )


if __name__ == "__main__":
    unittest.main()
