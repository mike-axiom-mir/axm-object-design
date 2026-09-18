import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build_source_box_face_atlas_layout_family as atlas_family


class SourceBoxFaceAtlasLayoutFamilyTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "schema": atlas_family.FAMILY_SCHEMA,
            "family_id": "object-source-box-face-atlas-layout-001",
            "retained_members": [
                {"surface_id": "lid_inner_service_surface", "uv_output": "lid.json"},
                {"surface_id": "front_service_panel_outer_service_surface", "uv_output": "front.json"},
            ],
        }
        self.contract = {
            "schema": atlas_family.MATERIALS_CONTRACT_SCHEMA,
            "asset_id": "modular-equipment-case-001",
            "atlas": {
                "width_px": 512,
                "height_px": 512,
                "pixels_per_meter": 500,
                "meters_per_pixel": 0.002,
                "review_uv_unit_m": 0.05,
                "texels_per_review_uv_unit": 25,
                "padding_px": 16,
                "filtering": "LINEAR_MIPMAP_ANISOTROPIC",
                "repeat": False,
            },
            "surfaces": [
                {"surface_id": "lid_inner_service_surface", "component_name": "lid_shell", "semantic": "interior_service_surface", "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V", "physical_size_m": [0.78, 0.48], "pixel_size": [390, 240], "rect_px": [16, 16, 390, 240]},
                {"surface_id": "front_service_panel_outer_service_surface", "component_name": "front_service_panel", "semantic": "exterior_service_surface", "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V", "physical_size_m": [0.468, 0.156], "pixel_size": [234, 78], "rect_px": [16, 288, 234, 78]},
            ],
            "truth_boundary": {key: False for key in ("source_geometry_changed", "source_surface_identities_changed", "source_material_slots_authored", "source_uv_authored", "production_uv_adopted", "production_texture_authored", "final_pixels_per_meter_accepted", "final_atlas_pack_accepted", "target_import_transport_accepted", "runtime_cost_accepted", "art_direction_final_accepted", "visual_qa_final_accepted", "canon", "production_ready")},
        }
        self.uvs = {
            "lid_inner_service_surface": self._uv("lid_inner_service_surface", "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V", [0.78, 0.48], [[0.0, 0.0], [15.6, 0.0], [15.6, 9.6], [0.0, 9.6]]),
            "front_service_panel_outer_service_surface": self._uv("front_service_panel_outer_service_surface", "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V", [0.468, 0.156], [[0.0, 0.0], [9.36, 0.0], [9.36, 3.12], [0.0, 3.12]]),
        }

    @staticmethod
    def _uv(surface_id, basis, physical, uvs):
        return {"schema": atlas_family.UV_OUTPUT_SCHEMA, "family_id": "object-source-box-face-uv-projection-001", "surface_id": surface_id, "variant_id": "materials_candidate_isotropic", "material_id": "service_dark", "basis": basis, "meters_per_uv_unit": [0.05, 0.05], "physical_span_m": physical, "density_anisotropy": 1.0, "source_face_mesh_digest": surface_id + "-mesh", "uv_payload_digest": surface_id + "-uv", "mesh": {"vertices": [[0, 0, 0]] * 4, "faces": [[0, 1, 2], [0, 2, 3]], "uvs": uvs}}

    def test_two_materially_different_surface_outputs(self):
        _, outputs = atlas_family.build_outputs(self.profile, self.contract, self.uvs)
        self.assertEqual(outputs[0]["pixel_size"], [390, 240])
        self.assertEqual(outputs[1]["pixel_size"], [234, 78])
        self.assertEqual(outputs[0]["padded_rect_px"], [0, 0, 422, 272])
        self.assertEqual(outputs[1]["padded_rect_px"], [0, 272, 266, 110])
        self.assertNotEqual(outputs[0]["atlas_uv_payload_digest"], outputs[1]["atlas_uv_payload_digest"])

    def test_contract_order_does_not_change_canonical_output(self):
        _, outputs = atlas_family.build_outputs(self.profile, self.contract, self.uvs)
        reversed_contract = copy.deepcopy(self.contract)
        reversed_contract["surfaces"].reverse()
        _, replay = atlas_family.build_outputs(self.profile, reversed_contract, self.uvs)
        self.assertEqual([row["output_digest"] for row in outputs], [row["output_digest"] for row in replay])

    def test_padded_overlap_fails_closed(self):
        broken = copy.deepcopy(self.contract)
        broken["surfaces"][1]["rect_px"][1] = 280
        with self.assertRaisesRegex(AssertionError, "padded Materials atlas islands overlap"):
            atlas_family.build_outputs(self.profile, broken, self.uvs)

    def test_uv_review_scale_drift_fails_closed(self):
        broken = copy.deepcopy(self.uvs)
        broken["lid_inner_service_surface"]["meters_per_uv_unit"][0] = 0.051
        with self.assertRaisesRegex(AssertionError, "review scale drift"):
            atlas_family.build_outputs(self.profile, self.contract, broken)

    def test_duplicate_surface_identity_fails_closed(self):
        broken = copy.deepcopy(self.contract)
        broken["surfaces"][1]["surface_id"] = broken["surfaces"][0]["surface_id"]
        with self.assertRaisesRegex(AssertionError, "duplicate Materials atlas surface identity"):
            atlas_family.build_outputs(self.profile, broken, self.uvs)


if __name__ == "__main__":
    unittest.main()
