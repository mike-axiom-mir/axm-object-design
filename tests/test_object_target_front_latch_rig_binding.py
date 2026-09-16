import copy
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
SOURCE_BINDING = ASSET / "front-latch-source-rig-binding-002.json"
INTERFACE = ASSET / "front-latch-pivot-interface-001.json"


class TargetFrontLatchRigBindingTests(unittest.TestCase):
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

    def _build(self, root: Path, **overrides):
        glb, receipt = self._fixture(root)
        kwargs = {
            "observed_source_rig_head": target_rig.SOURCE_RIG_HEAD,
            "observed_tech_art_head": target_rig.TECH_ART_HEAD,
            "observed_uc_head": target_rig.UC_HEAD,
        }
        kwargs.update(overrides)
        return target_rig.build_binding(
            SOURCE_BINDING,
            INTERFACE,
            receipt,
            glb,
            root / "binding.json",
            **kwargs,
        )

    def test_maps_exact_source_owned_latch_rig_to_target_handedness(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._build(Path(tmp))
        self.assertEqual(result["result"], target_rig.RESULT)
        self.assertEqual(result["representative_source_angles_deg"], [0.0, 25.0, 50.0])
        self.assertEqual(result["representative_target_angles_deg"], [-0.0, -25.0, -50.0])
        self.assertEqual(result["target_x_rotation_sign"], -1)
        self.assertEqual(result["stations"][0]["pivot_source_m"], [-0.22, -0.258, 0.2105])
        self.assertEqual(result["stations"][0]["pivot_target_m"], [-0.22, 0.2105, -0.258])
        self.assertEqual(result["stations"][1]["pivot_target_m"], [0.22, 0.2105, -0.258])
        self.assertFalse(result["truth_boundary"]["animationplayer_acceptance"])
        self.assertFalse(result["truth_boundary"]["runtime_controller_or_state_machine_acceptance"])

    def test_rejects_source_rig_head_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(AssertionError, "source Rigging donor head drift"):
                self._build(Path(tmp), observed_source_rig_head="0" * 40)

    def test_rejects_technical_art_head_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(AssertionError, "Technical Art donor head drift"):
                self._build(Path(tmp), observed_tech_art_head="0" * 40)

    def test_rejects_source_interface_byte_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            glb, receipt = self._fixture(root)
            bad_interface = root / "interface.json"
            value = json.loads(INTERFACE.read_text(encoding="utf-8"))
            value["stations"][0]["pivot_origin_m"][2] += 0.001
            bad_interface.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "source interface byte identity drift"):
                target_rig.build_binding(
                    SOURCE_BINDING,
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
