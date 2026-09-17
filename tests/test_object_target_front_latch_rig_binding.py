import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_object_target_front_latch_rig_binding as target_rig

ASSET = ROOT / "assets/modular-equipment-case-001"
INTERFACE = ASSET / "front-latch-pivot-interface-001.json"


class TargetFrontLatchRigBindingTests(unittest.TestCase):
    def _source_binding(self, root: Path, **mutations) -> Path:
        value = {
            "schema": "axm.object-front-latch-source-rig-binding/v0.2",
            "binding_id": "front-latch-source-rig-binding-003",
            "asset_id": "modular-equipment-case-001",
            "host_source_sha256": target_rig.SOURCE_SHA256,
            "source_mechanical_authority": {
                "repository": "mike-axiom-mir/axm-object-design",
                "pr": 17,
                "head": target_rig.SOURCE_MECHANICAL_AUTHORITY_HEAD,
                "pivot_interface": {
                    "path": "assets/modular-equipment-case-001/front-latch-pivot-interface-001.json",
                    "sha256": target_rig.SOURCE_INTERFACE_SHA256,
                },
                "capture_envelope": {
                    "path": "assets/modular-equipment-case-001/front-latch-capture-envelope-001.json",
                    "git_blob_sha": target_rig.SOURCE_CAPTURE_BLOB,
                    "required_result": "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_TO_CLEARANCE_ENVELOPE",
                },
                "role": "CURRENT_SOURCE_PIVOT_AND_PROOF_VOLUME_CAPTURE_AUTHORITY",
            },
            "historical_rigging_observation": {
                "head": "3b667ff5d30c46ec2fe7da7679518970f8610018",
                "role": "PROVENANCE_ONLY_NOT_CURRENT_INTERFACE_AUTHORITY",
            },
            "prior_rigging_binding": {
                "head": target_rig.PRIOR_RIGGING_HEAD,
                "role": "HISTORICAL_PRE_CAPTURE_ENVELOPE_CLASSIFICATION",
            },
            "joint_axis": [1.0, 0.0, 0.0],
            "pose_samples_deg": list(target_rig.EXPECTED_SOURCE_ANGLES),
            "required_capture_transition_bracket_deg": list(target_rig.EXPECTED_CAPTURE_BRACKET),
            "required_z_aabb_only_transition_bracket_deg": list(target_rig.EXPECTED_Z_AABB_BRACKET),
            "required_minimum_threshold_separation_deg": 39.0,
            "capture_semantics": {
                "z_aabb_transition": "BROAD_PHASE_AXIS_SEPARATION_ONLY_NOT_CAPTURE_THRESHOLD",
            },
        }
        value.update(mutations)
        path = root / "source-binding.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def _fixture(self, root: Path):
        glb = root / "target.glb"
        glb.write_bytes(b"bounded-target-fixture")
        receipt = {
            "schema": "axm.object-uc-rigid-scene-handoff/v0.1",
            "result": "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH",
            "source_repository_head": target_rig.TECH_ART_HEAD,
            "source_sha256": target_rig.SOURCE_SHA256,
            "observed_uc_commit": target_rig.UC_HEAD,
            "rebound_glb_sha256": hashlib.sha256(glb.read_bytes()).hexdigest(),
            "binary_geometry_payload_identical": True,
            "source_owned_fixed_levers": ["latch_0_lever", "latch_1_lever"],
            "source_owned_keeper_children": ["latch_0_keeper", "latch_1_keeper"],
            "graph_verification": {
                "parent_by_child": {
                    "latch_0_keeper": "lid_shell",
                    "latch_1_keeper": "lid_shell",
                }
            },
        }
        receipt_path = root / "receipt.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return glb, receipt_path

    def _build(self, root: Path, source_binding: Path | None = None, **overrides):
        glb, receipt = self._fixture(root)
        kwargs = {
            "observed_source_rig_head": target_rig.SOURCE_RIG_HEAD,
            "observed_tech_art_head": target_rig.TECH_ART_HEAD,
            "observed_uc_head": target_rig.UC_HEAD,
        }
        kwargs.update(overrides)
        return target_rig.build_binding(
            source_binding or self._source_binding(root),
            INTERFACE,
            receipt,
            glb,
            root / "binding.json",
            **kwargs,
        )

    def test_maps_exact_source_owned_boundary_schedule_to_target_handedness(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._build(Path(tmp))
        self.assertEqual(result["result"], target_rig.RESULT)
        self.assertEqual(result["representative_source_angles_deg"], target_rig.EXPECTED_SOURCE_ANGLES)
        self.assertEqual(result["representative_target_angles_deg"], [-0.0, -9.25, -9.30, -25.0, -48.65, -48.70, -50.0])
        self.assertEqual(result["source_capture_transition_bracket_deg"], [9.25, 9.30])
        self.assertEqual(result["target_capture_transition_bracket_x_deg"], [-9.30, -9.25])
        self.assertEqual(result["source_z_aabb_only_transition_bracket_deg"], [48.65, 48.70])
        self.assertEqual(result["target_z_aabb_only_transition_bracket_x_deg"], [-48.70, -48.65])
        self.assertEqual(result["target_x_rotation_sign"], -1)
        self.assertEqual(result["stations"][0]["pivot_source_m"], [-0.22, -0.258, 0.2105])
        self.assertEqual(result["stations"][0]["pivot_target_m"], [-0.22, 0.2105, -0.258])
        self.assertEqual(result["stations"][1]["pivot_target_m"], [0.22, 0.2105, -0.258])
        self.assertTrue(result["truth_boundary"]["proof_volume_capture_and_z_aabb_broad_phase_kept_distinct"])
        self.assertFalse(result["truth_boundary"]["animationplayer_acceptance"])
        self.assertFalse(result["truth_boundary"]["runtime_controller_or_state_machine_acceptance"])

    def test_rejects_source_rig_head_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(AssertionError, "source Rigging donor head drift"):
                self._build(Path(tmp), observed_source_rig_head="0" * 40)

    def test_rejects_capture_relabelled_as_z_aabb_bracket(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binding = self._source_binding(
                root,
                required_capture_transition_bracket_deg=list(target_rig.EXPECTED_Z_AABB_BRACKET),
            )
            with self.assertRaisesRegex(AssertionError, "source proof-volume capture bracket drift"):
                self._build(root, source_binding=binding)

    def test_rejects_source_interface_byte_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            glb, receipt = self._fixture(root)
            source_binding = self._source_binding(root)
            bad_interface = root / "interface.json"
            value = json.loads(INTERFACE.read_text(encoding="utf-8"))
            value["stations"][0]["pivot_origin_m"][2] += 0.001
            bad_interface.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "source interface byte identity drift"):
                target_rig.build_binding(
                    source_binding,
                    bad_interface,
                    receipt,
                    glb,
                    root / "binding.json",
                    observed_source_rig_head=target_rig.SOURCE_RIG_HEAD,
                    observed_tech_art_head=target_rig.TECH_ART_HEAD,
                    observed_uc_head=target_rig.UC_HEAD,
                )


if __name__ == "__main__":
    unittest.main()
