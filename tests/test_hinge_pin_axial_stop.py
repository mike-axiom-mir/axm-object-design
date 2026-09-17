import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_hinge_pin_axial_stop as axial

ASSET = ROOT / "assets/modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
CONTRACT_PATH = ASSET / "hinge-pin-axial-stop-001.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class HingePinAxialStopTests(unittest.TestCase):
    def verify(self, contract=CONTRACT, host_sha=None):
        return axial.verify(
            HOST,
            contract,
            host_sha=host_sha or axial.sha256(HOST_PATH),
            contract_sha=axial.sha256(CONTRACT_PATH),
        )

    def test_exact_source_owns_bilateral_axial_stop_overlay(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_HINGE_PIN_AXIAL_STOP_PROOF")
        self.assertEqual(receipt["overlay_component_count"], 2)
        self.assertFalse(receipt["host_source_geometry_changed"])
        self.assertAlmostEqual(receipt["minimum_observed_radial_overhang_m"], 0.004, places=12)
        self.assertAlmostEqual(receipt["minimum_observed_outer_knuckle_clearance_m"], 0.014, places=12)
        self.assertAlmostEqual(receipt["bilateral_symmetry_residual"], 0.0, places=12)

    def test_rejects_missing_bilateral_stop(self):
        bad = copy.deepcopy(CONTRACT)
        bad["stops"] = bad["stops"][:1]
        with self.assertRaisesRegex(AssertionError, "one left and one right stop"):
            self.verify(contract=bad)

    def test_rejects_insufficient_radial_overhang(self):
        bad = copy.deepcopy(CONTRACT)
        bad["stops"][0]["radius_m"] = 0.011
        with self.assertRaisesRegex(AssertionError, "radial overhang"):
            self.verify(contract=bad)

    def test_rejects_outer_knuckle_clearance_loss(self):
        bad = copy.deepcopy(CONTRACT)
        bad["stops"][0]["center_x_m"] = -0.338
        bad["stops"][0]["thickness_m"] = 0.024
        with self.assertRaisesRegex(AssertionError, "outer knuckle clearance"):
            self.verify(contract=bad)

    def test_rejects_host_source_identity_drift(self):
        with self.assertRaisesRegex(AssertionError, "host source identity mismatch"):
            self.verify(host_sha="0" * 64)


if __name__ == "__main__":
    unittest.main()
