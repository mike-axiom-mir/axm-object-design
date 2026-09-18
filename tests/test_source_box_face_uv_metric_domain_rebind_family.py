import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_source_box_face_uv_metric_domain_rebind_family as family

PROFILE = json.loads(
    (ROOT / "assets/modular-equipment-case-001/source-box-face-uv-metric-domain-rebind-family-001.json")
    .read_text(encoding="utf-8")
)
METRIC_HEAD = PROFILE["hard_surface_metric_donor"]["head"]

METRIC_CONTRACT = {
    "schema": family.METRIC_SCHEMA,
    "asset_id": "modular-equipment-case-001",
    "domains": [
        {
            "surface_id": "lid_inner_service_surface",
            "component_name": "lid_shell",
            "selector": "source_local_min_z_face",
            "origin_policy": "selected_face_center",
            "domain_units": "meters",
            "primary_extent_m": 0.78,
            "secondary_extent_m": 0.48,
            "primary_bounds_m": [-0.39, 0.39],
            "secondary_bounds_m": [-0.24, 0.24],
            "area_m2": 0.3744,
            "boundary_semantics": "CLOSED_RECTANGLE_ON_SELECTED_SOURCE_FACE",
        },
        {
            "surface_id": "front_service_panel_outer_service_surface",
            "component_name": "front_service_panel",
            "selector": "source_local_min_y_face",
            "origin_policy": "selected_face_center",
            "domain_units": "meters",
            "primary_extent_m": 0.468,
            "secondary_extent_m": 0.156,
            "primary_bounds_m": [-0.234, 0.234],
            "secondary_bounds_m": [-0.078, 0.078],
            "area_m2": 0.073008,
            "boundary_semantics": "CLOSED_RECTANGLE_ON_SELECTED_SOURCE_FACE",
        },
    ],
    "authority": {
        "hard_surface_owns_surface_metric_domain": True,
        "hard_surface_authors_uv": False,
        "hard_surface_selects_texel_density": False,
        "hard_surface_selects_atlas_dimensions": False,
        "hard_surface_selects_atlas_rectangles": False,
        "hard_surface_assigns_material": False,
    },
}


class SourceBoxFaceUvMetricDomainRebindFamilyTests(unittest.TestCase):
    def test_profile_is_bounded_and_pins_exact_metric_donor(self):
        donor = family.validate_profile(PROFILE, observed_metric_head=METRIC_HEAD)
        self.assertEqual(
            donor["git_blob_sha"],
            "2b425e2a12c648c20c2ad948f44489c4ac1a51e6",
        )
        self.assertEqual(set(PROFILE["retained_surface_ids"]), family.EXPECTED_SURFACES)
        self.assertEqual(PROFILE["parameter_contract"]["variants_per_surface"], 2)

    def test_two_materially_different_source_metric_domains_validate(self):
        domains = family.validate_metric_contract(METRIC_CONTRACT)
        self.assertEqual(domains["lid_inner_service_surface"]["primary_extent_m"], 0.78)
        self.assertEqual(domains["lid_inner_service_surface"]["secondary_extent_m"], 0.48)
        self.assertEqual(
            domains["front_service_panel_outer_service_surface"]["primary_extent_m"], 0.468
        )
        self.assertEqual(
            domains["front_service_panel_outer_service_surface"]["secondary_extent_m"], 0.156
        )

    def test_metric_domain_generates_expected_isotropic_uv_corners(self):
        domains = family.validate_metric_contract(METRIC_CONTRACT)
        generated = family.generate_metric_uv_corner_set(
            domains["lid_inner_service_surface"], [0.05, 0.05]
        )
        self.assertEqual(
            family.canonical_uvs(generated["uvs"]),
            [[0.0, 0.0], [0.0, 9.6], [15.6, 0.0], [15.6, 9.6]],
        )
        self.assertEqual([round(v, 12) for v in generated["uv_span"]], [15.6, 9.6])

    def test_metric_domain_generates_materially_different_anisotropic_variant(self):
        domains = family.validate_metric_contract(METRIC_CONTRACT)
        generated = family.generate_metric_uv_corner_set(
            domains["front_service_panel_outer_service_surface"], [0.05, 0.016666666666666666]
        )
        self.assertEqual([round(v, 12) for v in generated["uv_span"]], [9.36, 9.36])

    def test_metric_extent_drift_fails_closed(self):
        mutated = copy.deepcopy(METRIC_CONTRACT)
        mutated["domains"][0]["primary_extent_m"] += 0.001
        with self.assertRaisesRegex(AssertionError, "extent/bounds"):
            family.validate_metric_contract(mutated)

    def test_metric_center_drift_fails_closed(self):
        mutated = copy.deepcopy(METRIC_CONTRACT)
        mutated["domains"][1]["primary_bounds_m"][1] += 0.001
        mutated["domains"][1]["primary_extent_m"] += 0.001
        mutated["domains"][1]["area_m2"] = (
            mutated["domains"][1]["primary_extent_m"]
            * mutated["domains"][1]["secondary_extent_m"]
        )
        with self.assertRaisesRegex(AssertionError, "no longer centered"):
            family.validate_metric_contract(mutated)

    def test_metric_authority_drift_fails_closed(self):
        mutated = copy.deepcopy(METRIC_CONTRACT)
        mutated["authority"]["hard_surface_owns_surface_metric_domain"] = False
        with self.assertRaisesRegex(AssertionError, "authority missing"):
            family.validate_metric_contract(mutated)

    def test_metric_donor_head_drift_fails_closed(self):
        mutated = copy.deepcopy(PROFILE)
        mutated["hard_surface_metric_donor"]["head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "donor head drift"):
            family.validate_profile(mutated, observed_metric_head=METRIC_HEAD)


if __name__ == "__main__":
    unittest.main()
