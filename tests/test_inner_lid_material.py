from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_object_inner_lid_material_evidence import build_payload


class ObjectInnerLidMaterialTests(unittest.TestCase):
    def setUp(self):
        self.review = json.loads((ROOT / "lookdev/inner_lid_surface_review_001.json").read_text(encoding="utf-8"))
        self.base = {
            "schema": "axm.object-articulated-material-lookdev-payload/v0.2",
            "asset_id": "modular-equipment-case-001",
            "material_profile_sha256": self.review["base_material_profile_sha256"],
            "base_geometry_contract_sha256": self.review["base_geometry_contract_sha256"],
            "components": [
                {
                    "name": "lid_shell",
                    "kind": "box",
                    "center_m": [0.0, 0.0, 0.367],
                    "size_m": [0.78, 0.48, 0.11],
                    "role": "lid_shell",
                    "baseline_material": "neutral_proof",
                    "candidate_material": "shell_coating",
                },
                {
                    "name": "body_shell",
                    "kind": "box",
                    "center_m": [0.0, 0.0, 0.15],
                    "size_m": [0.78, 0.48, 0.30],
                    "role": "primary_shell",
                    "baseline_material": "neutral_proof",
                    "candidate_material": "shell_coating",
                },
            ],
            "materials": {
                "baseline": {
                    "neutral_proof": {"albedo": [0.46, 0.48, 0.49, 1.0], "albedo_hex": "#767A7DFF", "metallic": 0.08, "roughness": 0.78}
                },
                "candidate": {
                    "shell_coating": {"albedo": [0.247, 0.282, 0.306, 1.0], "albedo_hex": "#3F484EFF", "metallic": 0.42, "roughness": 0.54},
                    "service_dark": {"albedo": [0.145, 0.169, 0.184, 1.0], "albedo_hex": "#252B2FFF", "metallic": 0.18, "roughness": 0.66},
                },
            },
            "hinge_origin_m": [0.0, 0.252, 0.306],
            "direct_moving_component_roles": ["lid_shell", "hinge_knuckle_lid"],
            "rigid_owner_follow_component_names": ["latch_0_keeper", "latch_1_keeper"],
            "poses": [
                {"id": "closed", "open_angle_deg": 0.0, "mathematical_rotation_deg": 0.0},
                {"id": "mid_open", "open_angle_deg": 50.0, "mathematical_rotation_deg": -50.0},
                {"id": "peak_open", "open_angle_deg": 100.0, "mathematical_rotation_deg": -100.0},
            ],
            "camera_contexts": ["three_quarter", "rear_hinge"],
        }

    def write(self, folder: Path, name: str, value: dict) -> Path:
        path = folder / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def build(self, base: dict | None = None, review: dict | None = None):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            base_path = self.write(folder, "base.json", base or self.base)
            review_path = self.write(folder, "review.json", review or self.review)
            return build_payload(base_path, review_path)

    def test_existing_family_inner_lid_slot_is_bounded(self):
        payload, receipt = self.build()
        self.assertEqual(receipt["result"], "PASS_SOURCE_BOUND_INNER_LID_EXISTING_FAMILY_SLOT_PAYLOAD")
        self.assertEqual(receipt["component_name"], "lid_shell")
        self.assertEqual(receipt["surface_selector"], "source_local_min_z_face")
        self.assertEqual(receipt["control_material_id"], "shell_coating")
        self.assertEqual(receipt["candidate_material_id"], "service_dark")
        self.assertEqual(receipt["pose_ids"], ["mid_open", "peak_open"])
        self.assertEqual(receipt["pose_angles_deg"], [50.0, 100.0])
        self.assertFalse(receipt["new_material_scalars_authored"])
        self.assertFalse(receipt["source_geometry_changed"])
        self.assertTrue(payload["truth_boundary"]["review_representation_face_split_only"])
        self.assertFalse(payload["truth_boundary"]["source_material_slot_authored"])

    def test_material_profile_drift_fails_closed(self):
        broken = copy.deepcopy(self.base)
        broken["material_profile_sha256"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "material profile identity drift"):
            self.build(base=broken)

    def test_candidate_must_already_exist_in_material_family(self):
        broken = copy.deepcopy(self.review)
        broken["surface_review"]["candidate_material_id"] = "invented_inner_lid_material"
        with self.assertRaisesRegex(AssertionError, "material identity missing"):
            self.build(review=broken)

    def test_wrong_face_selector_fails_closed(self):
        broken = copy.deepcopy(self.review)
        broken["surface_review"]["surface_selector"] = "source_local_max_z_face"
        with self.assertRaisesRegex(AssertionError, "unsupported inner-lid face selector"):
            self.build(review=broken)

    def test_closed_pose_cannot_be_substituted(self):
        broken = copy.deepcopy(self.review)
        broken["pose_ids"] = ["closed", "peak_open"]
        with self.assertRaisesRegex(AssertionError, "requires an open pose"):
            self.build(review=broken)

    def test_new_material_scalars_are_forbidden(self):
        broken = copy.deepcopy(self.review)
        broken["surface_review"]["new_material_scalars_authored"] = True
        with self.assertRaisesRegex(AssertionError, "forbids new material scalars"):
            self.build(review=broken)


if __name__ == "__main__":
    unittest.main()
