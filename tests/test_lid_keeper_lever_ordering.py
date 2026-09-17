from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from verify_lid_keeper_lever_ordering import _rect_yz, _sat_separation_m


class KeeperLeverOrderingGeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.box = {
            "name": "box",
            "kind": "box",
            "center_m": [0.0, 0.0, 0.0],
            "size_m": [0.1, 0.1, 0.1],
        }

    def test_sat_reports_overlap_for_identical_boxes(self) -> None:
        a = _rect_yz(self.box, [0.0, 0.0, 0.0], 0.0)
        b = _rect_yz(self.box, [0.0, 0.0, 0.0], 0.0)
        self.assertLessEqual(_sat_separation_m(a, b), 0.0)

    def test_sat_reports_positive_gap_for_separated_boxes(self) -> None:
        shifted = dict(self.box)
        shifted["center_m"] = [0.0, 0.25, 0.0]
        a = _rect_yz(self.box, [0.0, 0.0, 0.0], 0.0)
        b = _rect_yz(shifted, [0.0, 0.0, 0.0], 0.0)
        self.assertAlmostEqual(_sat_separation_m(a, b), 0.15, places=12)

    def test_rotation_preserves_rectangle_size_and_overlap_identity(self) -> None:
        a = _rect_yz(self.box, [0.0, 0.0, 0.0], 37.0)
        b = _rect_yz(self.box, [0.0, 0.0, 0.0], 37.0)
        self.assertLessEqual(_sat_separation_m(a, b), 0.0)


if __name__ == "__main__":
    unittest.main()
