from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_object_lid_latch_runtime", ROOT / "tools" / "verify_object_lid_latch_runtime.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ObjectLidLatchRuntimeComparisonTests(unittest.TestCase):
    def contract(self):
        return {
            "schema": "axm.object-lid-latch-runtime-contract/v0.1",
            "asset_id": "modular-equipment-case-001",
            "materials_receiving_base": {"commit": "materials-head"},
            "animation_dependency": {"commit": "animation-head"},
            "lid_rig_dependency": {"commit": "lid-rig-head", "plan_digest": "lid-rig-digest"},
            "latch_rig_dependency": {"commit": "latch-rig-head", "plan_sha256": "latch-rig-digest"},
            "latch_ownership_dependency": {"commit": "ownership-head", "sha256": "ownership-digest"},
            "stress_cycles": 1,
            "capture_sample_indices": [0],
            "camera_contexts": ["three_quarter"],
            "required_display_sample_count": 100,
            "required_endpoint_inclusive_sample_count": 101,
            "required_moving_component_count": 7,
            "truth_boundary": {
                "synthetic_rebuild_control_not_product_path": True,
                "latch_pivot_is_review_only_rig_candidate": True,
                "physical_latch_mechanism": False,
                "target_device_fps_or_gpu_budget": False,
            },
        }

    def receipt(self, mode: str):
        moving = 7
        total_updates = 200
        constructions = moving * total_updates if mode == MODULE.CONTROL_MODE else moving
        return {
            "schema": "axm.object-lid-latch-runtime-observation/v0.1",
            "state": "PASS_TARGET_HOST_LID_LATCH_SAMPLED_RUNTIME_OBSERVATION",
            "mode": mode,
            "promotion_effect": "NONE",
            "asset_id": "modular-equipment-case-001",
            "source_sha256": "source",
            "sequence_id": "sequence",
            "sequence_digest": "sequence-digest",
            "sequence_geometry_digest": "sequence-geometry-digest",
            "base_clip_id": "clip",
            "base_clip_digest": "clip-digest",
            "animation_motion_evidence_head": "animation-head",
            "lid_rig_plan_digest": "lid-rig-digest",
            "latch_rig_dependency_head": "latch-rig-head",
            "latch_rig_plan_sha256": "latch-rig-digest",
            "ownership_dependency_head": "ownership-head",
            "ownership_contract_sha256": "ownership-digest",
            "materials_receiving_base": {"commit": "materials-head"},
            "static_component_count": 9,
            "moving_component_count": moving,
            "display_sample_count": 100,
            "endpoint_inclusive_sample_count": 101,
            "evidence_updates": 100,
            "stress_cycles": 1,
            "stress_updates": 100,
            "total_updates": total_updates,
            "resource_constructions": {
                "moving_nodes": constructions,
                "moving_meshes": constructions,
                "moving_materials": constructions,
            },
            "candidate_resource_identity_stable": True if mode == MODULE.CANDIDATE_MODE else None,
            "submission_timing_observation": {
                "combined": {
                    "count": total_updates,
                    "min_usec": 1,
                    "median_usec": 20 if mode == MODULE.CONTROL_MODE else 4,
                    "p95_usec": 40 if mode == MODULE.CONTROL_MODE else 8,
                    "max_usec": 60,
                    "total_usec": 4000 if mode == MODULE.CONTROL_MODE else 800,
                },
                "stress_sequence": {
                    "count": 100,
                    "min_usec": 1,
                    "median_usec": 18 if mode == MODULE.CONTROL_MODE else 4,
                    "p95_usec": 36 if mode == MODULE.CONTROL_MODE else 8,
                    "max_usec": 55,
                    "total_usec": 2000 if mode == MODULE.CONTROL_MODE else 400,
                },
            },
            "capture_sample_indices": [0],
            "camera_contexts": ["three_quarter"],
            "captures": {
                "0": {
                    "three_quarter": {
                        "state": "PASS",
                        "sha256": "same-frame",
                        "width": 820,
                        "height": 620,
                    }
                }
            },
            "selected_runtime_counters": {
                "0": {
                    "three_quarter": {
                        "draw_calls_in_frame": 16,
                        "objects_in_frame": 16,
                        "primitives_in_frame": 700,
                        "buffer_mem_bytes": 1000,
                        "texture_mem_bytes": 2000,
                    }
                }
            },
        }

    def test_passes_exact_heterogeneous_resource_reuse_contract(self):
        result = MODULE.compare_runtime(
            self.receipt(MODULE.CONTROL_MODE),
            self.receipt(MODULE.CANDIDATE_MODE),
            self.contract(),
            "runtime-head",
        )
        self.assertEqual(result["state"], MODULE.RESULT)
        self.assertAlmostEqual(result["measurements"]["moving_node_constructions"]["reduction_percent"], 99.5)
        self.assertEqual(result["workload"]["moving_component_count"], 7)
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
        candidate["selected_runtime_counters"]["0"]["three_quarter"]["draw_calls_in_frame"] = 17
        with self.assertRaisesRegex(AssertionError, "renderer submission counter drift"):
            MODULE.compare_runtime(control, candidate, self.contract(), "runtime-head")

    def test_fails_on_moving_component_count_drift(self):
        control = self.receipt(MODULE.CONTROL_MODE)
        candidate = self.receipt(MODULE.CANDIDATE_MODE)
        control["moving_component_count"] = 6
        candidate["moving_component_count"] = 6
        with self.assertRaisesRegex(AssertionError, "moving component count drift"):
            MODULE.compare_runtime(control, candidate, self.contract(), "runtime-head")


if __name__ == "__main__":
    unittest.main()
