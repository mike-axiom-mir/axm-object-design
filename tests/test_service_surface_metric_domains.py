import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_service_surface_metric_domains as domains

ASSET = ROOT / "assets/modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
METRIC_PATH = ASSET / "service-surface-metric-domains-001.json"
FRAME_PATH = ASSET / "service-surface-reference-frames-001.json"
LID_IDENTITY_PATH = ASSET / "lid-inner-surface-identity-001.json"
FRONT_IDENTITY_PATH = ASSET / "front-service-panel-outer-surface-identity-001.json"

HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
METRIC = json.loads(METRIC_PATH.read_text(encoding="utf-8"))
FRAMES = json.loads(FRAME_PATH.read_text(encoding="utf-8"))
LID_IDENTITY = json.loads(LID_IDENTITY_PATH.read_text(encoding="utf-8"))
FRONT_IDENTITY = json.loads(FRONT_IDENTITY_PATH.read_text(encoding="utf-8"))

MATERIALS_REVIEW = {
    "schema": "axm.object-service-dark-atlas-pack-review/v0.1",
    "asset_id": "modular-equipment-case-001",
    "surfaces": [
        {
            "surface_id": "lid_inner_service_surface",
            "component_name": "lid_shell",
            "semantic": "interior_service_surface",
            "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V",
            "physical_size_m": [0.78, 0.48],
            "pixel_size": [390, 240],
            "rect_px": [16, 16, 390, 240],
        },
        {
            "surface_id": "front_service_panel_outer_service_surface",
            "component_name": "front_service_panel",
            "semantic": "exterior_service_surface",
            "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V",
            "physical_size_m": [0.468, 0.156],
            "pixel_size": [234, 78],
            "rect_px": [16, 288, 234, 78],
        },
    ],
    "truth_boundary": {
        "source_geometry_changed": False,
        "source_surface_identities_changed": False,
        "source_material_slots_authored": False,
        "source_uv_authored": False,
        "production_uv_adopted": False,
    },
}


class ServiceSurfaceMetricDomainTests(unittest.TestCase):
    def verify(self, metric=METRIC, frames=FRAMES, materials=MATERIALS_REVIEW):
        return domains.verify(
            HOST,
            metric,
            frames,
            {
                "lid_inner_service_surface": LID_IDENTITY,
                "front_service_panel_outer_service_surface": FRONT_IDENTITY,
            },
            materials,
            host_sha=domains.sha256(HOST_PATH),
            metric_contract_sha=domains.sha256(METRIC_PATH),
            frame_contract_sha=domains.sha256(FRAME_PATH),
            identity_shas={
                "lid_inner_service_surface": domains.sha256(LID_IDENTITY_PATH),
                "front_service_panel_outer_service_surface": domains.sha256(FRONT_IDENTITY_PATH),
            },
        )

    def test_exact_source_owns_two_service_surface_metric_domains(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_SERVICE_SURFACE_METRIC_DOMAINS")
        self.assertEqual(receipt["host_vertices"], 468)
        self.assertEqual(receipt["host_triangles"], 812)
        self.assertEqual(receipt["domain_count"], 2)
        by_id = {row["surface_id"]: row for row in receipt["domains"]}
        lid = by_id["lid_inner_service_surface"]
        front = by_id["front_service_panel_outer_service_surface"]
        self.assertEqual(lid["origin_m"], [0.0, 0.0, 0.312])
        self.assertAlmostEqual(lid["primary_extent_m"], 0.78, places=12)
        self.assertAlmostEqual(lid["secondary_extent_m"], 0.48, places=12)
        self.assertEqual(lid["primary_bounds_m"], [-0.39, 0.39])
        self.assertEqual(lid["secondary_bounds_m"], [-0.24, 0.24])
        self.assertAlmostEqual(lid["area_m2"], 0.3744, places=12)
        self.assertEqual(front["origin_m"], [0.0, -0.258, 0.156])
        self.assertAlmostEqual(front["primary_extent_m"], 0.468, places=12)
        self.assertAlmostEqual(front["secondary_extent_m"], 0.156, places=12)
        self.assertEqual(front["primary_bounds_m"], [-0.234, 0.234])
        self.assertEqual(front["secondary_bounds_m"], [-0.078, 0.078])
        self.assertAlmostEqual(front["area_m2"], 0.073008, places=12)
        self.assertAlmostEqual(receipt["total_service_surface_area_m2"], 0.447408, places=12)
        self.assertTrue(receipt["materials_physical_sizes_match_source_domains"])
        self.assertFalse(receipt["production_uv_authored"])
        self.assertFalse(receipt["atlas_policy_adopted"])
        self.assertFalse(receipt["technical_art_transport_accepted"])
        self.assertFalse(receipt["runtime_representation_accepted"])

    def test_rejects_one_millimeter_metric_extent_drift(self):
        metric = copy.deepcopy(METRIC)
        metric["domains"][0]["primary_extent_m"] += 0.001
        with self.assertRaises(AssertionError):
            self.verify(metric=metric)

    def test_rejects_asymmetric_metric_bounds(self):
        metric = copy.deepcopy(METRIC)
        metric["domains"][1]["primary_bounds_m"][1] += 0.001
        with self.assertRaises(AssertionError):
            self.verify(metric=metric)

    def test_rejects_reference_frame_axis_drift(self):
        frames = copy.deepcopy(FRAMES)
        frames["frames"][0]["secondary_axis"] = [0, 0, 1]
        with self.assertRaises(AssertionError):
            self.verify(frames=frames)

    def test_rejects_materials_physical_size_redefinition(self):
        materials = copy.deepcopy(MATERIALS_REVIEW)
        materials["surfaces"][1]["physical_size_m"][0] += 0.001
        with self.assertRaises(AssertionError):
            self.verify(materials=materials)

    def test_rejects_uv_authority_expansion(self):
        metric = copy.deepcopy(METRIC)
        metric["authority"]["hard_surface_authors_uv"] = True
        with self.assertRaises(AssertionError):
            self.verify(metric=metric)

    def test_rejects_atlas_authority_expansion(self):
        metric = copy.deepcopy(METRIC)
        metric["authority"]["hard_surface_selects_atlas_rectangles"] = True
        with self.assertRaises(AssertionError):
            self.verify(metric=metric)


if __name__ == "__main__":
    unittest.main()
