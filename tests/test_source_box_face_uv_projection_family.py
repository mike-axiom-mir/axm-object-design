import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_source_box_face_uv_projection_family as family

PROFILE_PATH = ROOT / "assets/modular-equipment-case-001/source-box-face-uv-projection-family-001.json"
PROFILE = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
MATERIALS_HEAD = PROFILE["materials_donor"]["head"]


class SourceBoxFaceUvProjectionFamilyTests(unittest.TestCase):
    def test_family_is_bounded_to_two_surfaces_and_two_variants_each(self):
        members = family.validate_profile(PROFILE, observed_materials_head=MATERIALS_HEAD)
        self.assertEqual(len(members), 2)
        self.assertEqual(PROFILE["parameter_contract"]["variants_per_surface"], 2)
        self.assertEqual(
            [row["surface_id"] for row in members],
            ["lid_inner_service_surface", "front_service_panel_outer_service_surface"],
        )

    def test_basis_and_origin_parsing(self):
        self.assertEqual(
            family.parse_basis("SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V"),
            ("x", 0, "y", 1),
        )
        self.assertEqual(
            family.parse_basis("SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V"),
            ("x", 0, "z", 2),
        )
        self.assertEqual(family.parse_origin("SOURCE_FACE_MIN_X_MIN_Y"), ("x", "y"))
        self.assertEqual(family.parse_origin("SOURCE_FACE_MIN_X_MIN_Z"), ("x", "z"))

    def test_planar_projection_on_z_face(self):
        face = {
            "selector": "source_local_min_z_face",
            "component_name": "lid_shell",
            "surface_semantics": "interior_service_surface",
            "surface_id": "lid_inner_service_surface",
            "selected_surface_area_m2": 0.08,
            "mesh_digest": "mesh-z",
            "output_digest": "face-z",
            "hard_surface_authority_result": "PASS_SOURCE_OWNED_LID_INNER_SURFACE_IDENTITY",
            "mesh": {
                "vertices": [[-0.2, -0.1, 0.0], [0.2, -0.1, 0.0], [0.2, 0.1, 0.0], [-0.2, 0.1, 0.0]],
                "faces": [[0, 1, 2], [0, 2, 3]],
            },
        }
        config = {
            "selector": "source_local_min_z_face",
            "component_name": "lid_shell",
            "surface_semantics": "interior_service_surface",
            "material_id": "service_dark",
            "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V",
            "origin": "SOURCE_FACE_MIN_X_MIN_Y",
        }
        variant = {
            "id": "materials_candidate_isotropic",
            "meters_per_uv_unit_u": 0.05,
            "meters_per_uv_unit_v": 0.05,
            "source": "test",
        }
        output = family.project_variant(face, config, variant)
        self.assertEqual(output["physical_span_m"], [0.4, 0.2])
        self.assertEqual(output["uv_span"], [8.0, 4.0])
        self.assertEqual(output["basis_axes"], {"u": "x", "v": "y", "normal": "z"})
        self.assertEqual(output["density_anisotropy"], 1.0)

    def test_planar_projection_on_y_face_uses_xz_plane(self):
        face = {
            "selector": "source_local_min_y_face",
            "component_name": "front_service_panel",
            "surface_semantics": "exterior_service_surface",
            "surface_id": "front_service_panel_outer_service_surface",
            "selected_surface_area_m2": 0.06,
            "mesh_digest": "mesh-y",
            "output_digest": "face-y",
            "hard_surface_authority_result": "PASS_SOURCE_OWNED_FRONT_SERVICE_PANEL_OUTER_SURFACE_IDENTITY",
            "mesh": {
                "vertices": [[-0.15, 0.0, -0.1], [0.15, 0.0, -0.1], [0.15, 0.0, 0.1], [-0.15, 0.0, 0.1]],
                "faces": [[0, 1, 2], [0, 2, 3]],
            },
        }
        config = {
            "selector": "source_local_min_y_face",
            "component_name": "front_service_panel",
            "surface_semantics": "exterior_service_surface",
            "material_id": "service_dark",
            "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V",
            "origin": "SOURCE_FACE_MIN_X_MIN_Z",
        }
        variant = {
            "id": "three_x_v_density_stretch",
            "meters_per_uv_unit_u": 0.05,
            "meters_per_uv_unit_v": 1.0 / 60.0,
            "source": "test",
        }
        output = family.project_variant(face, config, variant)
        self.assertAlmostEqual(output["physical_span_m"][0], 0.3)
        self.assertAlmostEqual(output["physical_span_m"][1], 0.2)
        self.assertAlmostEqual(output["uv_span"][0], 6.0)
        self.assertAlmostEqual(output["uv_span"][1], 12.0)
        self.assertEqual(output["basis_axes"], {"u": "x", "v": "z", "normal": "y"})
        self.assertAlmostEqual(output["density_anisotropy"], 3.0)

    def test_face_normal_axis_in_basis_fails_closed(self):
        face = {
            "selector": "source_local_min_z_face",
            "component_name": "lid_shell",
            "surface_semantics": "interior_service_surface",
            "surface_id": "lid_inner_service_surface",
            "selected_surface_area_m2": 0.08,
            "mesh_digest": "mesh-z",
            "output_digest": "face-z",
            "hard_surface_authority_result": "PASS_SOURCE_OWNED_LID_INNER_SURFACE_IDENTITY",
            "mesh": {
                "vertices": [[-0.2, -0.1, 0.0], [0.2, -0.1, 0.0], [0.2, 0.1, 0.0], [-0.2, 0.1, 0.0]],
                "faces": [[0, 1, 2], [0, 2, 3]],
            },
        }
        config = {
            "selector": "source_local_min_z_face",
            "component_name": "lid_shell",
            "surface_semantics": "interior_service_surface",
            "material_id": "service_dark",
            "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V",
            "origin": "SOURCE_FACE_MIN_X_MIN_Z",
        }
        variant = {
            "id": "bad",
            "meters_per_uv_unit_u": 0.05,
            "meters_per_uv_unit_v": 0.05,
            "source": "test",
        }
        with self.assertRaisesRegex(AssertionError, "UV basis includes face-normal axis"):
            family.project_variant(face, config, variant)

    def test_nonpositive_density_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "nonpositive UV density scale"):
            family.validate_density_pair(0.05, 0.0, label="bad")

    def test_duplicate_surface_identity_fails_closed(self):
        mutated = copy.deepcopy(PROFILE)
        mutated["retained_members"][1]["surface_id"] = mutated["retained_members"][0]["surface_id"]
        with self.assertRaisesRegex(AssertionError, "duplicate retained UV surface identity"):
            family.validate_profile(mutated, observed_materials_head=MATERIALS_HEAD)

    def test_materials_head_drift_fails_closed(self):
        mutated = copy.deepcopy(PROFILE)
        mutated["materials_donor"]["head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "Materials donor head drift"):
            family.validate_profile(mutated, observed_materials_head=MATERIALS_HEAD)


if __name__ == "__main__":
    unittest.main()
