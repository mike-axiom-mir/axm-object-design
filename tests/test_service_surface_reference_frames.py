import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_service_surface_reference_frames as frames

ASSET = ROOT / "assets/modular-equipment-case-001"
HOST_PATH = ASSET / "source.json"
CONTRACT_PATH = ASSET / "service-surface-reference-frames-001.json"
LID_IDENTITY_PATH = ASSET / "lid-inner-surface-identity-001.json"
FRONT_IDENTITY_PATH = ASSET / "front-service-panel-outer-surface-identity-001.json"

HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
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


class ServiceSurfaceReferenceFrameTests(unittest.TestCase):
    def verify(self, contract=CONTRACT, lid=LID_IDENTITY, front=FRONT_IDENTITY, materials=MATERIALS_REVIEW):
        return frames.verify(
            HOST,
            contract,
            {
                "lid_inner_service_surface": lid,
                "front_service_panel_outer_service_surface": front,
            },
            materials,
            host_sha=frames.sha256(HOST_PATH),
            contract_sha=frames.sha256(CONTRACT_PATH),
            identity_shas={
                "lid_inner_service_surface": frames.sha256(LID_IDENTITY_PATH),
                "front_service_panel_outer_service_surface": frames.sha256(FRONT_IDENTITY_PATH),
            },
        )

    def test_exact_source_owns_two_service_surface_reference_frames(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_SERVICE_SURFACE_REFERENCE_FRAMES")
        self.assertEqual(receipt["host_vertices"], 468)
        self.assertEqual(receipt["host_triangles"], 812)
        self.assertEqual(receipt["frame_count"], 2)
        by_id = {row["surface_id"]: row for row in receipt["frames"]}
        lid = by_id["lid_inner_service_surface"]
        front = by_id["front_service_panel_outer_service_surface"]
        self.assertEqual(lid["primary_axis"], [1.0, 0.0, 0.0])
        self.assertEqual(lid["secondary_axis"], [0.0, 1.0, 0.0])
        self.assertEqual(lid["outward_normal"], [0.0, 0.0, -1.0])
        self.assertEqual(lid["orientation_parity"], -1)
        self.assertAlmostEqual(lid["primary_extent_m"], 0.78, places=12)
        self.assertAlmostEqual(lid["secondary_extent_m"], 0.48, places=12)
        self.assertEqual(front["primary_axis"], [1.0, 0.0, 0.0])
        self.assertEqual(front["secondary_axis"], [0.0, 0.0, 1.0])
        self.assertEqual(front["outward_normal"], [0.0, -1.0, 0.0])
        self.assertEqual(front["orientation_parity"], 1)
        self.assertAlmostEqual(front["primary_extent_m"], 0.468, places=12)
        self.assertAlmostEqual(front["secondary_extent_m"], 0.156, places=12)
        self.assertTrue(receipt["materials_basis_matches_source_frames"])
        self.assertFalse(receipt["production_uv_authored"])
        self.assertFalse(receipt["material_assignment_authored"])
        self.assertFalse(receipt["technical_art_transport_accepted"])

    def test_rejects_silent_primary_axis_mirror(self):
        contract = copy.deepcopy(CONTRACT)
        contract["frames"][0]["primary_axis"] = [-1, 0, 0]
        with self.assertRaises(AssertionError):
            self.verify(contract=contract)

    def test_rejects_selector_normal_disagreement(self):
        contract = copy.deepcopy(CONTRACT)
        contract["frames"][1]["outward_normal"] = [0, 1, 0]
        with self.assertRaises(AssertionError):
            self.verify(contract=contract)

    def test_rejects_downstream_basis_drift(self):
        materials = copy.deepcopy(MATERIALS_REVIEW)
        materials["surfaces"][1]["basis"] = "SOURCE_LOCAL_Z_TO_U__SOURCE_LOCAL_X_TO_V"
        with self.assertRaises(AssertionError):
            self.verify(materials=materials)

    def test_rejects_surface_identity_selector_drift(self):
        lid = copy.deepcopy(LID_IDENTITY)
        lid["selector"]["policy"] = "source_local_max_z_face"
        with self.assertRaises(AssertionError):
            self.verify(lid=lid)

    def test_rejects_hard_surface_uv_authority_expansion(self):
        contract = copy.deepcopy(CONTRACT)
        contract["authority"]["hard_surface_authors_uv"] = True
        with self.assertRaises(AssertionError):
            self.verify(contract=contract)

    def test_rejects_unowned_transport_promotion(self):
        contract = copy.deepcopy(CONTRACT)
        contract["authority"]["technical_art_transport_adopted"] = True
        with self.assertRaises(AssertionError):
            self.verify(contract=contract)


if __name__ == "__main__":
    unittest.main()
