import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_front_latch_ownership as latch

HOST_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
CONTRACT_PATH = ROOT / "assets/modular-equipment-case-001/front-latch-ownership-001.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class FrontLatchOwnershipTests(unittest.TestCase):
    def verify(self, host=HOST, contract=CONTRACT, host_sha=None):
        return latch.verify(
            host,
            contract,
            host_sha=host_sha or latch.sha256(HOST_PATH),
            contract_sha=latch.sha256(CONTRACT_PATH),
        )

    def test_exact_source_has_explicit_bilateral_latch_ownership(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_EXPLICIT_FRONT_LATCH_COMPONENT_OWNERSHIP")
        self.assertEqual(receipt["station_count"], 2)
        self.assertAlmostEqual(receipt["bilateral_x_residual_m"], 0.0)
        self.assertAlmostEqual(receipt["minimum_closed_keeper_lever_axis_overlap_m"], 0.011)
        self.assertAlmostEqual(receipt["minimum_lever_service_panel_axis_overlap_m"], 0.007)
        self.assertAlmostEqual(receipt["maximum_keeper_lid_front_face_gap_m"], 0.0)
        for row in receipt["station_results"]:
            self.assertEqual(row["keeper_owner_component"], "lid_shell")
            self.assertEqual(row["lever_owner_component"], "front_service_panel")
            self.assertGreater(min(row["closed_keeper_lever_overlap_m"].values()), 0.0)
            self.assertGreater(min(row["lever_panel_overlap_m"].values()), 0.0)
            self.assertGreater(row["keeper_lid_overlap_m"]["x"], 0.0)
            self.assertGreater(row["keeper_lid_overlap_m"]["z"], 0.0)

    def test_rejects_keeper_ownership_rewrite(self):
        bad = copy.deepcopy(CONTRACT)
        bad["stations"][0]["keeper_owner_component"] = "body_shell"
        with self.assertRaisesRegex(AssertionError, "keeper ownership drift"):
            self.verify(contract=bad)

    def test_rejects_latch_station_position_drift(self):
        bad = copy.deepcopy(CONTRACT)
        bad["stations"][1]["source_x_m"] = 0.221
        with self.assertRaisesRegex(AssertionError, "source_x mismatch"):
            self.verify(contract=bad)

    def test_rejects_host_source_identity_drift(self):
        with self.assertRaisesRegex(AssertionError, "host source identity mismatch"):
            self.verify(host_sha="0" * 64)

    def test_rejects_weakened_static_overlap_requirement(self):
        bad = copy.deepcopy(CONTRACT)
        bad["closed_relation"]["require_positive_keeper_lever_aabb_overlap"] = False
        with self.assertRaisesRegex(AssertionError, "keeper/lever positive-overlap requirement"):
            self.verify(contract=bad)


if __name__ == "__main__":
    unittest.main()
