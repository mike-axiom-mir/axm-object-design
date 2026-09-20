from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_exact_runtime", ROOT / "tools" / "verify_object_exact_uc_glb_resource_reuse.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

class ExactUcGlbResourceReuseTests(unittest.TestCase):
    def contract(self):
        return {
            "schema": MODULE.CONTRACT_SCHEMA,
            "historical_runtime_evidence": {"head": "old-runtime"},
            "receiving_technical_art_bridge_head": "ta-bridge",
            "technical_art": {"current_head": "ta", "historical_head": "old-ta", "uc_rigid_head": "uc", "rebound_glb_sha256": "g"*64},
            "target_rigging": {"current_latch_source_rig_head": "source-rig"},
            "animation_sequence": {"id": "seq", "digest": "s"*64, "duration_s": 2.5, "sample_rate_hz": 40, "endpoint_inclusive_sample_count": 101},
            "moving_components": ["lid_shell","hinge_lid_l0","hinge_lid_l1","latch_0_keeper","latch_1_keeper","latch_0_lever","latch_1_lever"],
            "workload": {"total_transform_updates": 2000, "stress_cycles": 20, "repeated_visible_samples_per_cycle": 100, "selected_capture_indices": [0,5,10,25,40,50,60,90,95,100]},
            "truth_boundary": {"historical_99_95_percent_reduction_is_not_transferred_to_exact_uc_glb": True, "synthetic_rebuild_control_on_exact_uc_glb": False},
        }

    def receipt(self):
        return {
            "schema": MODULE.RECEIPT_SCHEMA, "state": MODULE.RESULT, "animation_sequence_head": "runtime",
            "historical_runtime_head": "old-runtime", "receiving_technical_art_bridge_head": "ta-bridge",
            "technical_art_object_head": "ta", "technical_art_historical_head": "old-ta", "uc_commit": "uc", "glb_sha256": "g"*64,
            "lid_target_binding_result": "PASS_EXACT_LID_RIG_TO_UC_TARGET_BINDING_READY",
            "front_latch_target_binding_result": "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_ENVELOPE_TO_UC_TARGET_BINDING_READY",
            "current_latch_source_rig_head": "source-rig", "sequence_id": "seq", "sequence_digest": "s"*64,
            "sample_rate_hz": 40, "duration_s": 2.5, "endpoint_inclusive_sample_count": 101,
            "moving_component_count": 7, "moving_component_names": self.contract()["moving_components"],
            "resource_identity_stable": True, "observed_resource_replacements": 0,
            "direct_transform_stress_updates": 2000, "direct_transform_stress_cycles": 20, "repeated_visible_samples_per_cycle": 100,
            "neutral_pivot_wrapper_max_drift_m": 0.0, "max_lid_sample_seek_error_deg": 0.0, "max_latch_sample_seek_error_deg": 0.0,
            "endpoint_keeper_drift_m": 0.0, "endpoint_lever_drift_m": 0.0,
            "captures": {str(i): {} for i in range(10)},
            "truth_boundary": {
                "exact_uc_glb_moving_resource_identity_stable_across_2000_updates": True,
                "moving_node_mesh_material_replacement_observed": False,
                "historical_99_95_percent_reduction_transferred_to_exact_uc_glb": False,
            },
        }

    def test_accepts_bounded_current_exact_glb_reuse(self):
        out = MODULE.verify(self.contract(), self.receipt(), "runtime")
        self.assertEqual(out["result"], MODULE.RESULT)
        self.assertTrue(out["resource_identity_stable"])

    def test_rejects_resource_replacement(self):
        receipt = self.receipt()
        receipt["resource_identity_stable"] = False
        receipt["observed_resource_replacements"] = 1
        with self.assertRaises(AssertionError):
            MODULE.verify(self.contract(), receipt, "runtime")

    def test_rejects_historical_percentage_transfer(self):
        receipt = self.receipt()
        receipt["truth_boundary"]["historical_99_95_percent_reduction_transferred_to_exact_uc_glb"] = True
        with self.assertRaises(AssertionError):
            MODULE.verify(self.contract(), receipt, "runtime")

if __name__ == "__main__":
    unittest.main()
