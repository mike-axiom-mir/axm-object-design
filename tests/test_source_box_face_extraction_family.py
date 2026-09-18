import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_source_box_face_extraction_family as family

PROFILE_PATH = ROOT / "assets/modular-equipment-case-001/source-box-face-extraction-family-001.json"
PROFILE = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
DONOR_HEAD = PROFILE["hard_surface_donor"]["head"]


class SourceBoxFaceExtractionFamilyTests(unittest.TestCase):
    def test_family_is_bounded_and_cross_axis(self):
        members = family.validate_family(PROFILE, observed_head=DONOR_HEAD)
        self.assertEqual(len(members), 2)
        self.assertEqual(
            [row["surface_id"] for row in members],
            ["lid_inner_service_surface", "front_service_panel_outer_service_surface"],
        )
        self.assertEqual(
            {family.parse_selector(row["expected_selector"])[0] for row in members},
            {"y", "z"},
        )

    def test_exact_retained_selectors_parse(self):
        self.assertEqual(family.parse_selector("source_local_min_y_face"), ("y", 1, "min"))
        self.assertEqual(family.parse_selector("source_local_min_z_face"), ("z", 2, "min"))

    def test_unsupported_selector_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "unsupported source box-face selector"):
            family.parse_selector("source_local_diagonal_face")

    def test_duplicate_surface_identity_fails_closed(self):
        mutated = copy.deepcopy(PROFILE)
        mutated["retained_members"][1]["surface_id"] = mutated["retained_members"][0]["surface_id"]
        with self.assertRaisesRegex(AssertionError, "duplicate retained surface identity"):
            family.validate_family(mutated, observed_head=DONOR_HEAD)

    def test_donor_head_drift_fails_closed(self):
        mutated = copy.deepcopy(PROFILE)
        mutated["hard_surface_donor"]["head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "Hard-Surface donor head drift"):
            family.validate_family(mutated, observed_head=DONOR_HEAD)

    def test_member_bound_cannot_widen_silently(self):
        mutated = copy.deepcopy(PROFILE)
        mutated["parameter_contract"]["maximum_members"] = 3
        with self.assertRaisesRegex(AssertionError, "family member bound drift"):
            family.validate_family(mutated, observed_head=DONOR_HEAD)

    def test_compact_mesh_preserves_authority_face_order(self):
        host_mesh = {
            "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [9, 9, 9]],
            "faces": [[0, 1, 2], [0, 2, 3], [0, 4, 1]],
        }
        receipt = {
            "selected_vertex_indices": [0, 1, 2, 3],
            "selected_unique_vertex_count": 4,
            "selected_global_face_indices": [0, 1],
            "selected_triangle_count": 2,
        }
        mesh = family.compact_surface_mesh(host_mesh, receipt)
        self.assertEqual(mesh["vertices"], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]])
        self.assertEqual(mesh["faces"], [[0, 1, 2], [0, 2, 3]])
        self.assertEqual(family.verify_plane(mesh, "source_local_min_z_face"), ("z", "min", 0.0))


if __name__ == "__main__":
    unittest.main()
