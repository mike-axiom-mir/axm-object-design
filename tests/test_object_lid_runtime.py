from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_object_lid_runtime", ROOT / "tools" / "verify_object_lid_runtime.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ObjectLidRuntimeComparisonTests(unittest.TestCase):
    def contract(self):
        return {
            "schema": "axm.object-lid-runtime-contract/v0.1",
            "asset_id": "modular-equipment-case-001",
            "materials_receiving_base": {"commit": "materials-head"},
            "animation_dependency": {"commit": "animation-head"},
            "rig_dependency": {"commit": "rig-head", "plan_digest": "rig-digest"},
            "stress_cycles": 2,
            "capture_sample_indices": [0],
            "camera_contexts": ["three_quarter"],
            "required_display_sample_count": 80,
            "truth_boundary": {
                "synthetic_rebuild_control_not_product_path": True,
                "target_device_fps_or_gpu_budget": False,
            },
        }

    def receipt(self, mode: str):
        moving = 2
        total_updates = 240
        constructions = moving * total_updates if mode == MODULE.CONTROL_MODE else moving
        return {
            "schema": "axm.object-lid-runtime-observation/v0.1",
            "state": "PASS_TARGET_HOST_LID_SAMPLED_RUNTIME_OBSERVATION",
            "mode": mode,
            "promotion_effect": "NONE",
            "asset_id": "modular-equipment-case-001",
            "source_sha256": "source",
            "clip_id": "clip",
            "clip_digest": "clip-digest",
            "rig_plan_digest": "rig-digest",
            "animation_motion_evidence_head": "animation-head",
            "materials_receiving_base": {"commit": "materials-head"},
            "animation_dependency": {"commit": "animation-head"},
            "rig_dependency": {"commit": "rig-head"},
            "static_component_count": 10,
            "moving_component_count": moving,
            "display_sample_count": 80,
            "evidence_updates": 80,
            "stress_cycles": 2,
            "stress_updates": 160,
            "total_updates": total_updates,
            "resource_constructions": {
                "moving_nodes": constructions,
                "moving_meshes": constructions,
                "moving_materials": constructions,
            },
            "candidate_resource_identity_stable": True if mode == MODULE.CANDIDATE_MODE else None,
            "submission_timing_observation": {
                "combined": {"count": total_updates, "min_usec": 1, "median_usec": 10 if mode == MODULE.CONTROL_MODE else 2, "p95_usec": 20 if mode == MODULE.CONTROL_MODE else 4, "max_usec": 30, "total_usec": 2400 if mode == MODULE.CONTROL_MODE else 480},
                "stress_sequence": {"count": 160, "min_usec": 1, "median_usec": 9 if mode == MODULE.CONTROL_MODE else 2, "p95_usec": 18 if mode == MODULE.CONTROL_MODE else 4, "max_usec": 25, "total_usec": 1600 if mode == MODULE.CONTROL_MODE else 320},
            },
            "capture_sample_indices": [0],
            "camera_contexts": ["three_quarter"],
            "captures": {
                "0": {
                    "three_quarter": {"state": "PASS", "sha256": "same-frame", "width": 820, "height": 620}
                }
            },
            "selected_runtime_counters": {
                "0": {
                    "three_quarter": {
                        "draw_calls_in_frame": 12,
                        "objects_in_frame": 12,
                        "primitives_in_frame": 500,
                        "buffer_mem_bytes": 1000,
                        "texture_mem_bytes": 2000,
                    }
                }
            },
        }

    def test_passes_exact_resource_reuse_contract(self):
        result = MODULE.compare_runtime(
            self.receipt(MODULE.CONTROL_MODE),
            self.receipt(MODULE.CANDIDATE_MODE),
            self.contract(),
            "runtime-head",
        )
        self.assertEqual(result["state"], MODULE.RESULT)
        self.assertAlmostEqual(result["measurements"]["moving_node_constructions"]["reduction_percent"], 99.58333333333333)
        self.assertEqual(result["visual_tradeoff_for_art_director"], "NONE_OBSERVED_IN_EXACT_RETAINED_PROOF_FRAMES")

    def test_fails_on_visual_drift(self):
        control = self.receipt(MODULE.CONTROL_MODE)
        candidate = self.receipt(MODULE.CANDIDATE_MODE)
        candidate["captures"]["0"]["three_quarter"]["sha256"] = "different-frame"
        with self.assertRaisesRegex(AssertionError, "visual byte drift"):
            MODULE.compare_runtime(control, candidate, self.contract(), "runtime-head")

    def test_fails_on_submission_counter_drift(self):
        control = self.receipt(MODULE.CONTROL_MODE)
        candidate = self.receipt(MODULE.CANDIDATE_MODE)
        candidate["selected_runtime_counters"]["0"]["three_quarter"]["draw_calls_in_frame"] = 13
        with self.assertRaisesRegex(AssertionError, "renderer submission counter drift"):
            MODULE.compare_runtime(control, candidate, self.contract(), "runtime-head")


if __name__ == "__main__":
    unittest.main()
