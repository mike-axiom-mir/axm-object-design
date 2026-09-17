import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_lid_inner_surface_identity as surface

ASSET = ROOT / "assets/modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
CONTRACT_PATH = ASSET / "lid-inner-surface-identity-001.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
REVIEW = {
    "schema": "axm.object-inner-lid-material-review/v0.1",
    "asset_id": "modular-equipment-case-001",
    "surface_review": {
        "component_name": "lid_shell",
        "required_role": "lid_shell",
        "required_kind": "box",
        "surface_selector": "source_local_min_z_face",
        "control_material_id": "shell_coating",
        "candidate_material_id": "service_dark",
    },
    "truth_boundary": {
        "source_geometry_changed": False,
        "source_material_slot_authored": False,
    },
}


class LidInnerSurfaceIdentityTests(unittest.TestCase):
    def verify(self, contract=CONTRACT, review=REVIEW):
        return surface.verify(
            HOST,
            contract,
            review,
            host_sha=surface.sha256(HOST_PATH),
            contract_sha=surface.sha256(CONTRACT_PATH),
        )

    def test_exact_source_owns_only_inward_lid_face_identity(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_LID_INNER_SURFACE_IDENTITY")
        self.assertEqual(receipt["host_vertices"], 468)
        self.assertEqual(receipt["host_triangles"], 812)
        self.assertEqual(receipt["lid_group_face_count"], 12)
        self.assertEqual(receipt["selected_face_offsets"], [0, 1])
        self.assertEqual(receipt["selected_triangle_count"], 2)
        self.assertEqual(receipt["selected_unique_vertex_count"], 4)
        self.assertAlmostEqual(receipt["selected_plane_z_m"], 0.312, places=12)
        self.assertAlmostEqual(receipt["opposite_plane_z_m"], 0.422, places=12)
        self.assertAlmostEqual(receipt["selected_surface_area_m2"], 0.3744, places=12)
        self.assertAlmostEqual(receipt["lid_to_body_gap_m"], 0.012, places=12)
        self.assertTrue(receipt["materials_review_selector_matches"])
        self.assertFalse(receipt["host_geometry_changed"])
        self.assertFalse(receipt["material_assignment_authored"])
        self.assertFalse(receipt["materials_review_candidate_adopted"])

    def test_rejects_surface_selector_drift(self):
        bad = copy.deepcopy(CONTRACT)
        bad["selector"]["policy"] = "source_local_max_z_face"
        with self.assertRaisesRegex(AssertionError, "surface selector drift"):
            self.verify(contract=bad)

    def test_rejects_materials_review_selector_drift(self):
        bad = copy.deepcopy(REVIEW)
        bad["surface_review"]["surface_selector"] = "source_local_max_z_face"
        with self.assertRaisesRegex(AssertionError, "Materials review selector drift"):
            self.verify(review=bad)

    def test_rejects_hard_surface_material_assignment(self):
        bad = copy.deepcopy(CONTRACT)
        bad["material_authority"]["hard_surface_assigns_material"] = True
        bad["material_authority"]["source_material_assignment"] = "service_dark"
        with self.assertRaisesRegex(AssertionError, "Hard Surface must not assign final material"):
            self.verify(contract=bad)

    def test_rejects_review_candidate_adoption_without_art_qa(self):
        bad = copy.deepcopy(CONTRACT)
        bad["material_authority"]["review_material_candidate_adopted"] = True
        with self.assertRaisesRegex(AssertionError, "must remain unadopted"):
            self.verify(contract=bad)

    def test_rejects_host_source_identity_drift(self):
        bad = copy.deepcopy(CONTRACT)
        bad["host_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "host source identity mismatch"):
            self.verify(contract=bad)

    def test_rejects_component_identity_drift(self):
        bad = copy.deepcopy(CONTRACT)
        bad["component_name"] = "body_shell"
        with self.assertRaisesRegex(AssertionError, "component identity drift"):
            self.verify(contract=bad)


if __name__ == "__main__":
    unittest.main()
