import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_front_latch_keeper_seat as seat

HOST_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
OWNERSHIP_PATH = ROOT / "assets/modular-equipment-case-001/front-latch-ownership-001.json"
CONTRACT_PATH = ROOT / "assets/modular-equipment-case-001/front-latch-keeper-seat-001.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
OWNERSHIP = json.loads(OWNERSHIP_PATH.read_text(encoding="utf-8"))
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class FrontLatchKeeperSeatTests(unittest.TestCase):
    def verify(self, host=HOST, ownership=OWNERSHIP, contract=CONTRACT, host_sha=None, ownership_sha=None):
        return seat.verify(
            host,
            ownership,
            contract,
            host_sha=host_sha or seat.sha256(HOST_PATH),
            ownership_sha=ownership_sha or seat.sha256(OWNERSHIP_PATH),
            contract_sha=seat.sha256(CONTRACT_PATH),
        )

    def test_exact_source_has_bilateral_keeper_attachment_seats(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_FRONT_LATCH_KEEPER_ATTACHMENT_SEATS")
        self.assertEqual(receipt["station_count"], 2)
        self.assertAlmostEqual(receipt["minimum_seat_area_m2"], 0.00172, places=12)
        self.assertAlmostEqual(receipt["maximum_owner_volume_penetration_m"], 0.0, places=12)
        self.assertAlmostEqual(receipt["bilateral_x_center_residual_m"], 0.0, places=12)
        self.assertAlmostEqual(receipt["bilateral_plane_residual_m"], 0.0, places=12)
        self.assertAlmostEqual(receipt["bilateral_z_center_residual_m"], 0.0, places=12)
        self.assertAlmostEqual(receipt["bilateral_area_residual_m2"], 0.0, places=12)
        for row in receipt["station_results"]:
            self.assertEqual(row["owner_component"], "lid_shell")
            self.assertAlmostEqual(row["plane_coordinate_m"], -0.24, places=12)
            self.assertAlmostEqual(row["dimensions_m"][0], 0.08, places=12)
            self.assertAlmostEqual(row["dimensions_m"][1], 0.0215, places=12)
            self.assertAlmostEqual(row["center_m"][2], 0.32275, places=12)

    def test_rejects_ownership_drift(self):
        bad = copy.deepcopy(OWNERSHIP)
        bad["stations"][0]["keeper_owner_component"] = "body_shell"
        with self.assertRaisesRegex(AssertionError, "keeper owner drift"):
            self.verify(ownership=bad)

    def test_rejects_declared_seat_metric_drift(self):
        bad = copy.deepcopy(CONTRACT)
        bad["stations"][0]["dimensions_m"][1] += 0.001
        with self.assertRaisesRegex(AssertionError, "seat dimensions"):
            self.verify(contract=bad)

    def test_rejects_declared_face_plane_drift(self):
        bad = copy.deepcopy(CONTRACT)
        bad["stations"][1]["plane_coordinate_m"] += 0.001
        with self.assertRaisesRegex(AssertionError, "declared seat plane"):
            self.verify(contract=bad)

    def test_rejects_attachment_authority_expansion(self):
        bad = copy.deepcopy(CONTRACT)
        bad["authority"]["retention_force_defined"] = True
        with self.assertRaisesRegex(AssertionError, "authority expansion forbidden"):
            self.verify(contract=bad)

    def test_rejects_source_identity_drift(self):
        with self.assertRaisesRegex(AssertionError, "host source identity mismatch"):
            self.verify(host_sha="0" * 64)

    def test_rejects_ownership_identity_drift(self):
        with self.assertRaisesRegex(AssertionError, "ownership contract identity mismatch"):
            self.verify(ownership_sha="0" * 64)


if __name__ == "__main__":
    unittest.main()
