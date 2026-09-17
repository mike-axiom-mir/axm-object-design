import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_front_service_panel_outer_surface_identity as surface

ASSET = ROOT / "assets/modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
CONTRACT_PATH = ASSET / "front-service-panel-outer-surface-identity-001.json"
HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
REVIEW = {
    "schema": "axm.object-front-service-panel-uv-review/v0.1",
    "asset_id": "modular-equipment-case-001",
    "target": {
        "component_name": "front_service_panel",
        "component_role": "service_panel",
        "component_kind": "box",
        "review_surface_selector": "source_local_min_y_face",
        "source_surface_identity_owned": False,
        "source_material_slot_authored": False,
        "material_id": "service_dark",
    },
    "uv_candidate": {
        "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V",
        "meters_per_uv_unit_u": 0.05,
        "meters_per_uv_unit_v": 0.05,
    },
    "truth_boundary": {
        "source_geometry_changed": False,
        "source_surface_identity_owned": False,
        "source_material_slot_authored": False,
        "production_uv_authored": False,
    },
}


class FrontServicePanelOuterSurfaceIdentityTests(unittest.TestCase):
    def verify(self, contract=CONTRACT, review=REVIEW):
        return surface.verify(
            HOST,
            contract,
            review,
            host_sha=surface.sha256(HOST_PATH),
            contract_sha=surface.sha256(CONTRACT_PATH),
        )

    def test_exact_source_owns_only_outward_front_service_panel_face_identity(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_FRONT_SERVICE_PANEL_OUTER_SURFACE_IDENTITY")
        self.assertEqual(receipt["host_vertices"], 468)
        self.assertEqual(receipt["host_triangles"], 812)
        self.assertEqual(receipt["panel_group_face_count"], 12)
        self.assertEqual(receipt["selected_face_offsets"], [4, 5])
        self.assertEqual(receipt["selected_triangle_count"], 2)
        self.assertEqual(receipt["selected_unique_vertex_count"], 4)
        self.assertAlmostEqual(receipt["selected_plane_y_m"], -0.258, places=12)
        self.assertAlmostEqual(receipt["opposite_plane_y_m"], -0.240, places=12)
        self.assertAlmostEqual(receipt["body_front_plane_y_m"], -0.240, places=12)
        self.assertAlmostEqual(receipt["selected_surface_area_m2"], 0.073008, places=12)
        self.assertAlmostEqual(receipt["panel_depth_m"], 0.018, places=12)
        self.assertAlmostEqual(receipt["body_contact_residual_m"], 0.0, places=12)
        self.assertTrue(receipt["materials_review_selector_matches"])
        self.assertFalse(receipt["host_geometry_changed"])
        self.assertFalse(receipt["material_assignment_authored"])
        self.assertFalse(receipt["production_uv_authored"])
        self.assertFalse(receipt["materials_uv_candidate_adopted"])

    def test_rejects_surface_selector_drift(self):
        bad = copy.deepcopy(CONTRACT)
        bad["selector"]["policy"] = "source_local_max_y_face"
        with self.assertRaisesRegex(AssertionError, "surface selector drift"):
            self.verify(contract=bad)

    def test_rejects_materials_review_selector_drift(self):
        bad = copy.deepcopy(REVIEW)
        bad["target"]["review_surface_selector"] = "source_local_max_y_face"
        with self.assertRaisesRegex(AssertionError, "Materials UV review selector drift"):
            self.verify(review=bad)

    def test_rejects_hard_surface_material_assignment(self):
        bad = copy.deepcopy(CONTRACT)
        bad["material_authority"]["hard_surface_assigns_material"] = True
        bad["material_authority"]["source_material_assignment"] = "service_dark"
        with self.assertRaisesRegex(AssertionError, "Hard Surface must not assign final material"):
            self.verify(contract=bad)

    def test_rejects_hard_surface_uv_assignment(self):
        bad = copy.deepcopy(CONTRACT)
        bad["uv_authority"]["hard_surface_authors_uv"] = True
        bad["uv_authority"]["source_uv_assignment"] = "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V"
        with self.assertRaisesRegex(AssertionError, "Hard Surface must not author production UVs"):
            self.verify(contract=bad)

    def test_rejects_review_uv_candidate_adoption(self):
        bad = copy.deepcopy(CONTRACT)
        bad["uv_authority"]["review_uv_candidate_adopted"] = True
        with self.assertRaisesRegex(AssertionError, "must remain unadopted"):
            self.verify(contract=bad)

    def test_rejects_materials_premature_source_surface_ownership(self):
        bad = copy.deepcopy(REVIEW)
        bad["target"]["source_surface_identity_owned"] = True
        with self.assertRaisesRegex(AssertionError, "must not pre-own source surface identity"):
            self.verify(review=bad)

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
