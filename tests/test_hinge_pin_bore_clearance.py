from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from tools.verify_hinge_pin_bore_clearance import RESULT, evaluate

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "assets/modular-equipment-case-001/source.json"
CONTRACT = ROOT / "assets/modular-equipment-case-001/hinge-pin-bore-clearance-001.json"


def _load():
    host = json.loads(HOST.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    sha = hashlib.sha256(HOST.read_bytes()).hexdigest()
    return host, contract, sha


class HingePinBoreClearanceTests(unittest.TestCase):
    def test_exact_contract_passes(self):
        host, contract, sha = _load()
        receipt = evaluate(host, contract, observed_host_sha256=sha)
        self.assertEqual(receipt["result"], RESULT)
        self.assertAlmostEqual(receipt["radial_clearance_m"], 0.001, places=12)
        self.assertAlmostEqual(receipt["remaining_knuckle_wall_m"], 0.011, places=12)
        self.assertEqual(receipt["knuckle_count"], 5)
        self.assertEqual(receipt["candidate_pin_shell_overlap_volume_m3"], 0.0)
        self.assertFalse(receipt["host_source_geometry_changed"])
        self.assertGreater(receipt["source_solid_pin_knuckle_overlap_volume_m3"], 0.0)

    def test_zero_clearance_fails_closed(self):
        host, contract, sha = _load()
        bad = copy.deepcopy(contract)
        bad["bore_radius_m"] = host["hinge"]["pin_radius"]
        with self.assertRaisesRegex(AssertionError, "insufficient bore-to-pin radial clearance"):
            evaluate(host, bad, observed_host_sha256=sha)

    def test_minimum_wall_fails_closed(self):
        host, contract, sha = _load()
        bad = copy.deepcopy(contract)
        bad["bore_radius_m"] = 0.012
        with self.assertRaisesRegex(AssertionError, "insufficient knuckle wall"):
            evaluate(host, bad, observed_host_sha256=sha)

    def test_axis_drift_fails_closed(self):
        host, contract, sha = _load()
        bad = copy.deepcopy(contract)
        bad["hinge_axis"] = [0, 1, 0]
        with self.assertRaisesRegex(AssertionError, "hinge axis drift"):
            evaluate(host, bad, observed_host_sha256=sha)

    def test_source_identity_drift_fails_closed(self):
        host, contract, _ = _load()
        with self.assertRaisesRegex(AssertionError, "host source identity drift"):
            evaluate(host, contract, observed_host_sha256="0" * 64)

    def test_segment_drift_fails_closed(self):
        host, contract, sha = _load()
        bad_host = copy.deepcopy(host)
        bad_host["hinge"]["segments"] = 16
        with self.assertRaisesRegex(AssertionError, "hinge segmentation drift"):
            evaluate(bad_host, contract, observed_host_sha256=sha)


if __name__ == "__main__":
    unittest.main()
