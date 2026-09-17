import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_source_box_face_indexed_uv_binding_family as family

PROFILE = json.loads(
    (ROOT / "assets/modular-equipment-case-001/source-box-face-indexed-uv-binding-family-001.json")
    .read_text(encoding="utf-8")
)


def face(surface_id, component_name, global_faces, global_vertices, axis="z"):
    return {
        "schema": family.FACE_SCHEMA,
        "surface_id": surface_id,
        "component_name": component_name,
        "selector": f"source_local_min_{axis}_face",
        "hard_surface_authority_result": "PASS_SOURCE_OWNED_TEST_SURFACE",
        "source_global_face_indices": list(global_faces),
        "source_global_vertex_indices": list(global_vertices),
        "mesh": {
            "vertices": [[0, 0, 0], [2, 0, 0], [2, 1, 0], [0, 1, 0]],
            "faces": [[0, 1, 2], [0, 2, 3]],
        },
        "truth_boundary": {
            "source_geometry_changed": False,
            "material_or_uv_assignment": False,
        },
    }


def frame_payload(source_face, variant_id, uvs, basis):
    return {
        "schema": family.SOURCE_FRAME_SCHEMA,
        "surface_id": source_face["surface_id"],
        "variant_id": variant_id,
        "hard_surface_frame_head": "1" * 40,
        "exact_previous_output_match": True,
        "rebound_uv_output_digest": family.digest_json([source_face["surface_id"], variant_id, uvs]),
        "projection": {
            "basis": basis,
            "basis_axes": {"u": "x", "v": "y", "normal": "z"},
            "physical_span_m": [2.0, 1.0],
            "meters_per_uv_unit": [0.05, 0.05],
            "uv_span": [40.0, 20.0],
            "mesh": {
                "vertices": copy.deepcopy(source_face["mesh"]["vertices"]),
                "faces": copy.deepcopy(source_face["mesh"]["faces"]),
                "uvs": copy.deepcopy(uvs),
            },
        },
    }


def metric_payload(source_face, variant_id, uvs):
    return {
        "schema": family.METRIC_SCHEMA,
        "surface_id": source_face["surface_id"],
        "variant_id": variant_id,
        "hard_surface_metric_head": "2" * 40,
        "exact_source_metric_binding": True,
        "source_metric_domain": {
            "component_name": source_face["component_name"],
            "primary_extent_m": 2.0,
            "secondary_extent_m": 1.0,
            "area_m2": 2.0,
        },
        "previous_uv_corner_set": copy.deepcopy(uvs),
        "metric_generated_uv_corner_set": list(reversed(copy.deepcopy(uvs))),
        "metric_uv_corner_set_digest": family.digest_json(family.canonical_uvs(uvs)),
        "max_uv_corner_residual": 0.0,
    }


class IndexedUVBindingFamilyTests(unittest.TestCase):
    def setUp(self):
        self.lid = face(
            "lid_inner_service_surface", "lid_shell", [100, 101], [10, 11, 12, 13], "z"
        )
        self.front = face(
            "front_service_panel_outer_service_surface",
            "front_service_panel",
            [200, 201],
            [20, 21, 22, 23],
            "y",
        )
        self.candidate_uvs = [[0, 0], [4, 0], [4, 2], [0, 2]]
        self.negative_uvs = [[0, 0], [4, 0], [4, 6], [0, 6]]

    def test_profile_pins_exact_existing_prerequisites(self):
        observed = family.validate_profile(PROFILE, repo_root=ROOT)
        self.assertEqual(set(observed), {"source_face_family", "source_frame_family", "metric_rebind_family"})

    def test_two_surfaces_four_materially_different_bindings(self):
        outputs = []
        for source_face, basis in (
            (self.lid, "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V"),
            (self.front, "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V"),
        ):
            for variant_id, uvs in (
                ("materials_candidate_isotropic", self.candidate_uvs),
                ("negative_three_x_v", self.negative_uvs),
            ):
                outputs.append(
                    family.build_binding(
                        source_face,
                        frame_payload(source_face, variant_id, uvs, basis),
                        metric_payload(source_face, variant_id, uvs),
                    )
                )
        self.assertTrue(family.validate_surface_disjointness({
            self.lid["surface_id"]: self.lid,
            self.front["surface_id"]: self.front,
        }))
        self.assertEqual(len({row["segmentation_digest"] for row in outputs}), 2)
        self.assertEqual(len({row["uv_binding_digest"] for row in outputs}), 4)
        self.assertEqual(len({row["output_digest"] for row in outputs}), 4)
        self.assertEqual(family.canonical_family_digest(outputs), family.canonical_family_digest(list(reversed(outputs))))
        self.assertEqual({tuple(row["source_global_face_indices"]) for row in outputs}, {(100, 101), (200, 201)})

    def test_source_triangle_overlap_fails_closed(self):
        bad = copy.deepcopy(self.front)
        bad["source_global_face_indices"][0] = 100
        with self.assertRaisesRegex(AssertionError, "overlap"):
            family.validate_surface_disjointness({self.lid["surface_id"]: self.lid, bad["surface_id"]: bad})

    def test_duplicate_source_vertex_identity_fails_closed(self):
        bad = copy.deepcopy(self.lid)
        bad["source_global_vertex_indices"][1] = bad["source_global_vertex_indices"][0]
        with self.assertRaisesRegex(AssertionError, "global vertex"):
            family.validate_face(bad, surface_id=bad["surface_id"])

    def test_source_frame_uv_cardinality_and_topology_fail_closed(self):
        record = family.validate_face(self.lid, surface_id=self.lid["surface_id"])
        bad_uv = frame_payload(
            self.lid,
            "materials_candidate_isotropic",
            self.candidate_uvs[:-1],
            "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V",
        )
        with self.assertRaisesRegex(AssertionError, "UV vertex cardinality"):
            family.validate_source_frame_payload(bad_uv, surface_id=self.lid["surface_id"], face_record=record)
        bad_topology = frame_payload(
            self.lid,
            "materials_candidate_isotropic",
            self.candidate_uvs,
            "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V",
        )
        bad_topology["projection"]["mesh"]["faces"][0] = [0, 1, 3]
        with self.assertRaisesRegex(AssertionError, "topology"):
            family.validate_source_frame_payload(bad_topology, surface_id=self.lid["surface_id"], face_record=record)

    def test_metric_binding_drift_fails_closed(self):
        frame_row = frame_payload(
            self.lid,
            "materials_candidate_isotropic",
            self.candidate_uvs,
            "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V",
        )
        face_record = family.validate_face(self.lid, surface_id=self.lid["surface_id"])
        validated_frame = family.validate_source_frame_payload(
            frame_row, surface_id=self.lid["surface_id"], face_record=face_record
        )
        bad = metric_payload(self.lid, "materials_candidate_isotropic", self.candidate_uvs)
        bad["previous_uv_corner_set"][0][0] += 0.001
        with self.assertRaisesRegex(AssertionError, "previous UV"):
            family.validate_metric_payload(bad, surface_id=self.lid["surface_id"], frame_record=validated_frame)

    def test_current_world_adoption_policy_cannot_be_enabled(self):
        bad = copy.deepcopy(PROFILE)
        bad["parameter_contract"]["automatic_current_world_adoption"] = "ALLOWED"
        with self.assertRaisesRegex(AssertionError, "forbidden policy"):
            family.validate_profile(bad, repo_root=ROOT)


if __name__ == "__main__":
    unittest.main()
