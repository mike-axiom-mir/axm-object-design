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
                    "neutral_proof": {
                        "albedo": [0.46, 0.48, 0.49, 1.0],
                        "albedo_hex": "#767A7DFF",
                        "metallic": 0.08,
                        "roughness": 0.78,
                    }
                },
                "candidate": {
                    "shell_coating": {
                        "albedo": [0.247, 0.282, 0.306, 1.0],
                        "albedo_hex": "#3F484EFF",
                        "metallic": 0.42,
                        "roughness": 0.54,
                    },
                    "service_dark": {
                        "albedo": [0.145, 0.169, 0.184, 1.0],
                        "albedo_hex": "#252B2FFF",
                        "metallic": 0.18,
                        "roughness": 0.66,
                    },
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
        self.source_identity = {
            "schema": "axm.object-hard-surface-surface-identity/v0.1",
            "asset_id": "modular-equipment-case-001",
            "host_source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
            "surface_id": "lid_inner_service_surface",
            "component_name": "lid_shell",
            "required_role": "lid_shell",
            "required_kind": "box",
            "surface_semantics": "interior_service_surface",
            "selector": {
                "policy": "source_local_min_z_face",
                "expected_triangle_count": 2,
                "expected_unique_vertex_count": 4,
            },
            "review_provenance": {
                "repository": "mike-axiom-mir/axm-object-design",
                "pull_request": 6,
                "head": self.review["source_surface_identity"]["review_parent_head"],
                "path": "lookdev/inner_lid_surface_review_001.json",
                "git_blob_sha": self.review["source_surface_identity"]["review_parent_git_blob_sha"],
                "review_schema": "axm.object-inner-lid-material-review/v0.1",
                "review_selector": "source_local_min_z_face",
                "relationship": "surface identity only; no material preference or Materials acceptance inherited",
            },
            "material_authority": {
                "hard_surface_assigns_material": False,
                "source_material_assignment": "UNASSIGNED",
                "review_material_candidate_adopted": False,
            },
            "truth_boundary": {
                "host_source_geometry_changed": False,
                "surface_identity_source_owned": True,
                "material_slot_identity_only": True,
                "material_assignment": False,
                "materials_candidate_adopted": False,
                "uvs": False,
                "textures": False,
                "decals": False,
                "wear": False,
                "bevel_or_normal_change": False,
                "engine_import_acceptance": False,
                "runtime_performance_acceptance": False,
                "art_direction_acceptance": False,
                "visual_qa_acceptance": False,
                "canon": False,
                "production_readiness": False,
            },
        }

    def write(self, folder: Path, name: str, value: dict) -> Path:
        path = folder / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def build(
        self,
        base: dict | None = None,
        review: dict | None = None,
        source_identity: dict | None = None,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            base_path = self.write(folder, "base.json", base or self.base)
            review_path = self.write(folder, "review.json", review or self.review)
            source_path = self.write(folder, "source-identity.json", source_identity or self.source_identity)
            return build_payload(base_path, review_path, source_path)

    def test_source_owned_existing_family_inner_lid_rebind_is_bounded(self):
        payload, receipt = self.build()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_INNER_LID_EXISTING_FAMILY_SLOT_REBIND")
        self.assertEqual(receipt["source_surface_id"], "lid_inner_service_surface")
        self.assertEqual(receipt["source_surface_head"], self.review["source_surface_identity"]["head"])
        self.assertEqual(receipt["source_surface_git_blob_sha"], self.review["source_surface_identity"]["git_blob_sha"])
        self.assertEqual(receipt["component_name"], "lid_shell")
        self.assertEqual(receipt["surface_selector"], "source_local_min_z_face")
        self.assertEqual(receipt["control_material_id"], "shell_coating")
        self.assertEqual(receipt["candidate_material_id"], "service_dark")
        self.assertEqual(receipt["pose_ids"], ["mid_open", "peak_open"])
        self.assertEqual(receipt["pose_angles_deg"], [50.0, 100.0])
        self.assertFalse(receipt["new_material_scalars_authored"])
        self.assertFalse(receipt["source_geometry_changed"])
        self.assertTrue(receipt["source_surface_identity_owned"])
        self.assertFalse(receipt["source_material_assignment_authored"])
        self.assertFalse(receipt["materials_candidate_adopted_as_source_material"])
        self.assertEqual(payload["source_surface_identity"]["material_assignment"], "UNASSIGNED")
        self.assertFalse(payload["source_surface_identity"]["materials_candidate_adopted_by_source"])
        self.assertTrue(payload["truth_boundary"]["review_representation_face_split_only"])

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

    def test_source_surface_id_drift_fails_closed(self):
        broken = copy.deepcopy(self.source_identity)
        broken["surface_id"] = "lid_outer_surface"
        with self.assertRaisesRegex(AssertionError, "source surface id drift"):
            self.build(source_identity=broken)

    def test_source_surface_selector_drift_fails_closed(self):
        broken = copy.deepcopy(self.source_identity)
        broken["selector"]["policy"] = "source_local_max_z_face"
        with self.assertRaisesRegex(AssertionError, "source surface selector drift"):
            self.build(source_identity=broken)

    def test_source_material_assignment_fails_closed(self):
        broken = copy.deepcopy(self.source_identity)
        broken["material_authority"]["hard_surface_assigns_material"] = True
        broken["material_authority"]["source_material_assignment"] = "service_dark"
        with self.assertRaisesRegex(AssertionError, "must not assign final material"):
            self.build(source_identity=broken)

    def test_source_candidate_adoption_fails_closed(self):
        broken = copy.deepcopy(self.source_identity)
        broken["material_authority"]["review_material_candidate_adopted"] = True
        with self.assertRaisesRegex(AssertionError, "must remain unadopted"):
            self.build(source_identity=broken)

    def test_source_review_parent_lineage_drift_fails_closed(self):
        broken = copy.deepcopy(self.source_identity)
        broken["review_provenance"]["head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "source surface review parent head drift"):
            self.build(source_identity=broken)


if __name__ == "__main__":
    unittest.main()
