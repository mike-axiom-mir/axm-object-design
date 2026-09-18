import copy
import json
import unittest
from pathlib import Path

from tools.build_source_box_face_indexed_atlas_uv_binding_family import (
    EXACT_VARIANT,
    compose_surface,
    validate_family_disjointness,
    validate_profile,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "assets/modular-equipment-case-001/source-box-face-indexed-atlas-uv-binding-family-001.json"


def make_indexed(surface_id, faces, vertices, basis, span, review_uvs):
    local_faces = [[0, 1, 2], [0, 2, 3]]
    triangle_bindings = []
    for face_offset, local_face in enumerate(local_faces):
        triangle_bindings.append(
            {
                "local_face_index": face_offset,
                "source_global_face_index": faces[face_offset],
                "source_global_vertex_indices": [vertices[i] for i in local_face],
                "corners": [
                    {"source_global_vertex_index": vertices[i], "uv": review_uvs[i]}
                    for i in local_face
                ],
            }
        )
    return {
        "schema": "axm.object-derived-source-box-face-indexed-uv-binding/v0.1",
        "surface_id": surface_id,
        "component_name": "lid_shell" if surface_id.startswith("lid_") else "front_service_panel",
        "variant_id": EXACT_VARIANT,
        "basis": basis,
        "physical_span_m": span,
        "source_global_face_indices": faces,
        "source_global_vertex_indices": vertices,
        "source_vertex_uv_bindings": [
            {"local_vertex_index": i, "source_global_vertex_index": vertices[i], "uv": review_uvs[i]}
            for i in range(4)
        ],
        "triangle_corner_bindings": triangle_bindings,
        "segmentation_digest": f"seg-{surface_id}",
        "uv_binding_digest": f"uv-{surface_id}",
        "output_digest": f"indexed-{surface_id}",
    }


def make_atlas(surface_id, basis, span, pixel_size, rect, local_pixels):
    atlas_uvs = [[(rect[0] + x) / 512.0, (rect[1] + y) / 512.0] for x, y in local_pixels]
    return {
        "schema": "axm.object-derived-source-box-face-atlas-layout/v0.1",
        "family_id": "object-source-box-face-atlas-layout-001",
        "surface_id": surface_id,
        "component_name": "lid_shell" if surface_id.startswith("lid_") else "front_service_panel",
        "basis": basis,
        "physical_size_m": span,
        "review_meters_per_uv_unit": [0.05, 0.05],
        "pixels_per_meter": 500,
        "pixel_size": pixel_size,
        "rect_px": rect,
        "padded_rect_px": [rect[0] - 16, rect[1] - 16, pixel_size[0] + 32, pixel_size[1] + 32],
        "local_pixel_vertices": local_pixels,
        "atlas_uvs": atlas_uvs,
        "faces": [[0, 1, 2], [0, 2, 3]],
        "atlas_uv_payload_digest": f"atlas-{surface_id}",
        "output_digest": f"atlas-output-{surface_id}",
    }


class IndexedAtlasUVBindingFamilyTests(unittest.TestCase):
    def setUp(self):
        self.lid_indexed = make_indexed(
            "lid_inner_service_surface", [12, 13], [8, 9, 10, 11],
            "SOURCE_X_TO_U__SOURCE_Y_TO_V", [0.78, 0.48],
            [[0.0, 0.0], [15.6, 0.0], [15.6, 9.6], [0.0, 9.6]],
        )
        self.lid_atlas = make_atlas(
            "lid_inner_service_surface", "SOURCE_X_TO_U__SOURCE_Y_TO_V",
            [0.78, 0.48], [390, 240], [16, 16, 390, 240],
            [[0, 0], [390, 0], [390, 240], [0, 240]],
        )
        self.front_indexed = make_indexed(
            "front_service_panel_outer_service_surface", [28, 29], [16, 17, 20, 21],
            "SOURCE_X_TO_U__SOURCE_Z_TO_V", [0.468, 0.156],
            [[0.0, 0.0], [9.36, 0.0], [9.36, 3.12], [0.0, 3.12]],
        )
        self.front_atlas = make_atlas(
            "front_service_panel_outer_service_surface", "SOURCE_X_TO_U__SOURCE_Z_TO_V",
            [0.468, 0.156], [234, 78], [16, 288, 234, 78],
            [[0, 0], [234, 0], [234, 78], [0, 78]],
        )

    def test_profile_pins_exact_predecessors_and_forbids_adoption(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        observed = validate_profile(profile, repo_root=ROOT)
        self.assertEqual(set(observed), {"indexed_uv_family", "atlas_layout_family"})
        self.assertEqual(profile["parameter_contract"]["automatic_current_world_uv0_adoption"], "FORBIDDEN")

    def test_two_materially_different_source_index_to_atlas_bindings(self):
        lid = compose_surface(self.lid_indexed, self.lid_atlas)
        front = compose_surface(self.front_indexed, self.front_atlas)
        self.assertTrue(validate_family_disjointness([lid, front]))
        self.assertNotEqual(lid["basis"], front["basis"])
        self.assertNotEqual(lid["atlas"]["rect_px"], front["atlas"]["rect_px"])
        self.assertNotEqual(lid["indexed_atlas_binding_digest"], front["indexed_atlas_binding_digest"])
        self.assertEqual([row["source_global_vertex_index"] for row in lid["source_vertex_atlas_uv_bindings"]], [8, 9, 10, 11])
        self.assertEqual([row["source_global_vertex_index"] for row in front["source_vertex_atlas_uv_bindings"]], [16, 17, 20, 21])
        self.assertLessEqual(lid["maximum_review_uv_reconstruction_residual"], 1e-12)
        self.assertLessEqual(front["maximum_review_uv_reconstruction_residual"], 1e-12)
        self.assertLessEqual(lid["maximum_atlas_uv_reconstruction_residual"], 1e-12)
        self.assertLessEqual(front["maximum_atlas_uv_reconstruction_residual"], 1e-12)

    def test_one_pixel_review_mapping_drift_fails_closed(self):
        atlas = copy.deepcopy(self.lid_atlas)
        atlas["local_pixel_vertices"][1][0] += 1
        with self.assertRaisesRegex(AssertionError, "review UV"):
            compose_surface(self.lid_indexed, atlas)

    def test_topology_drift_fails_closed(self):
        atlas = copy.deepcopy(self.front_atlas)
        atlas["faces"][0] = [0, 1, 3]
        with self.assertRaisesRegex(AssertionError, "topology"):
            compose_surface(self.front_indexed, atlas)

    def test_duplicate_source_vertex_identity_fails_closed(self):
        indexed = copy.deepcopy(self.lid_indexed)
        indexed["source_global_vertex_indices"][1] = indexed["source_global_vertex_indices"][0]
        with self.assertRaisesRegex(AssertionError, "vertex identity"):
            compose_surface(indexed, self.lid_atlas)


if __name__ == "__main__":
    unittest.main()
