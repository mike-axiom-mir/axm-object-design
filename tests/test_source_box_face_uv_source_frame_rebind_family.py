import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_source_box_face_uv_source_frame_rebind_family as family

PROFILE = json.loads((ROOT / "assets/modular-equipment-case-001/source-box-face-uv-source-frame-rebind-family-001.json").read_text(encoding="utf-8"))
HARD_SURFACE_HEAD = PROFILE["hard_surface_frame_donor"]["head"]

FRAME_CONTRACT = {
    "schema": family.FRAME_SCHEMA,
    "asset_id": "modular-equipment-case-001",
    "frames": [
        {
            "surface_id": "lid_inner_service_surface",
            "component_name": "lid_shell",
            "selector": "source_local_min_z_face",
            "origin_policy": "selected_face_center",
            "primary_axis": [1, 0, 0],
            "secondary_axis": [0, 1, 0],
            "outward_normal": [0, 0, -1],
            "orientation_parity": -1,
        },
        {
            "surface_id": "front_service_panel_outer_service_surface",
            "component_name": "front_service_panel",
            "selector": "source_local_min_y_face",
            "origin_policy": "selected_face_center",
            "primary_axis": [1, 0, 0],
            "secondary_axis": [0, 0, 1],
            "outward_normal": [0, -1, 0],
            "orientation_parity": 1,
        },
    ],
    "downstream_basis_observation": {
        "expected_materials_basis": {
            "lid_inner_service_surface": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V",
            "front_service_panel_outer_service_surface": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V",
        }
    },
    "authority": {
        "hard_surface_owns_surface_reference_frame": True,
        "hard_surface_authors_uv": False,
        "hard_surface_assigns_material": False,
    },
}


class SourceBoxFaceUvSourceFrameRebindFamilyTests(unittest.TestCase):
    def test_profile_is_bounded_and_pins_exact_frame_donor(self):
        donor = family.validate_profile(PROFILE, observed_hard_surface_head=HARD_SURFACE_HEAD)
        self.assertEqual(donor["git_blob_sha"], "ffb0671eac025f0d39eeb412b58e0ae017e21d99")
        self.assertEqual(set(PROFILE["retained_surface_ids"]), family.EXPECTED_SURFACES)
        self.assertEqual(PROFILE["parameter_contract"]["variants_per_surface"], 2)

    def test_two_materially_different_source_frames_derive_expected_bases(self):
        frames = family.validate_frame_contract(FRAME_CONTRACT)
        self.assertEqual(frames["lid_inner_service_surface"]["basis"], "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V")
        self.assertEqual(frames["front_service_panel_outer_service_surface"]["basis"], "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V")
        self.assertEqual(frames["lid_inner_service_surface"]["basis_axes"], {"u": "x", "v": "y", "normal": "z"})
        self.assertEqual(frames["front_service_panel_outer_service_surface"]["basis_axes"], {"u": "x", "v": "z", "normal": "y"})

    def test_materials_density_origin_stays_separate_from_source_frame_authority(self):
        frames = family.validate_frame_contract(FRAME_CONTRACT)
        materials = {
            "surface_id": "lid_inner_service_surface",
            "component_name": "lid_shell",
            "selector": "source_local_min_z_face",
            "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V",
            "origin": "SOURCE_FACE_MIN_X_MIN_Y",
            "candidate": {"meters_per_uv_unit_u": 0.05, "meters_per_uv_unit_v": 0.05},
        }
        rebound = family.derive_source_frame_config(materials, frames["lid_inner_service_surface"])
        self.assertEqual(rebound["basis"], materials["basis"])
        self.assertEqual(rebound["origin"], "SOURCE_FACE_MIN_X_MIN_Y")
        self.assertEqual(rebound["candidate"], materials["candidate"])

    def test_noncardinal_frame_fails_closed(self):
        mutated = copy.deepcopy(FRAME_CONTRACT)
        mutated["frames"][0]["primary_axis"] = [0.5, 0.5, 0]
        with self.assertRaisesRegex(AssertionError, "exact positive cardinal axis"):
            family.validate_frame_contract(mutated)

    def test_orientation_parity_drift_fails_closed(self):
        mutated = copy.deepcopy(FRAME_CONTRACT)
        mutated["frames"][0]["orientation_parity"] = 1
        with self.assertRaisesRegex(AssertionError, "parity/outward-normal"):
            family.validate_frame_contract(mutated)

    def test_duplicate_frame_identity_fails_closed(self):
        mutated = copy.deepcopy(FRAME_CONTRACT)
        mutated["frames"][1]["surface_id"] = mutated["frames"][0]["surface_id"]
        with self.assertRaisesRegex(AssertionError, "surface set drift"):
            family.validate_frame_contract(mutated)

    def test_materials_basis_conflict_fails_closed(self):
        frames = family.validate_frame_contract(FRAME_CONTRACT)
        materials = {
            "surface_id": "lid_inner_service_surface",
            "component_name": "lid_shell",
            "selector": "source_local_min_z_face",
            "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V",
        }
        with self.assertRaisesRegex(AssertionError, "conflicts with source-owned"):
            family.derive_source_frame_config(materials, frames["lid_inner_service_surface"])

    def test_hard_surface_head_drift_fails_closed(self):
        mutated = copy.deepcopy(PROFILE)
        mutated["hard_surface_frame_donor"]["head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "donor head drift"):
            family.validate_profile(mutated, observed_hard_surface_head=HARD_SURFACE_HEAD)


if __name__ == "__main__":
    unittest.main()
