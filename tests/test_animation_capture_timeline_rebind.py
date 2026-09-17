from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "verify_animation_capture_timeline_rebind.py"
SPEC = importlib.util.spec_from_file_location("verify_animation_capture_timeline_rebind", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class AnimationCaptureTimelineRebindTests(unittest.TestCase):
    def setUp(self) -> None:
        self.asset = "modular-equipment-case-001"
        self.host_sha = "source-sha"
        self.rig_head = "rig-head"
        self.source_head = "source-head"
        self.binding_blob = "binding-blob"
        self.policy_blob = "policy-blob"
        self.sequence_digest = "sequence-digest"
        self.contract = {
            "schema": mod.CONTRACT_SCHEMA,
            "asset_id": self.asset,
            "host_source_sha256": self.host_sha,
            "animation_sequence": {
                "sequence_id": "lid-latch-open-hold-close-001",
                "sequence_digest": self.sequence_digest,
                "sample_rate_hz": 40,
                "duration_s": 2.5,
                "endpoint_inclusive_sample_count": 101,
                "terminal_latch_angle_deg": 50.0,
            },
            "current_rigging_authority": {
                "exact_head": self.rig_head,
                "binding_git_blob_sha": self.binding_blob,
                "required_result": "PASS_SOURCE_OWNED_FRONT_LATCH_RIG_CAPTURE_ENVELOPE_REBIND",
            },
            "source_capture_authority": {
                "exact_head": self.source_head,
                "policy_git_blob_sha": self.policy_blob,
                "required_result": "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_TO_CLEARANCE_ENVELOPE",
                "required_capture_transition_deg_range": [9.2647, 9.2649],
                "required_z_aabb_only_transition_deg_range": [48.6647, 48.6649],
                "z_aabb_semantics": "BROAD_PHASE_AXIS_SEPARATION_ONLY_NOT_CAPTURE_THRESHOLD",
            },
            "preservation_contract": {
                "retimed": False,
                "keys_changed": False,
                "easing_changed": False,
                "amplitude_changed": False,
                "source_geometry_changed": False,
                "rig_pivots_changed": False,
                "rig_motion_envelope_changed": False,
            },
            "truth_boundary": {
                "animation_timeline_characterization_owned": True,
                "proof_volume_capture_boundary_is_physical_retention": False,
                "z_aabb_boundary_is_capture_threshold": False,
                "continuous_release_forces_proven": False,
                "continuous_reengagement_forces_proven": False,
                "runtime_controller_accepted": False,
                "gameplay_accepted": False,
                "final_visual_motion_accepted": False,
                "canon_or_production_ready": False,
            },
        }
        samples = []
        for index in range(101):
            if index <= 10:
                lid = 0.0
            elif index < 90:
                lid = 10.0
            else:
                lid = 0.0
            samples.append({
                "index": index,
                "time_s": index / 40.0,
                "lid_open_angle_deg": lid,
                "latch_lever_angle_deg": mod._expected_latch_angle(index),
            })
        self.sequence = {
            "schema": mod.SEQUENCE_EVIDENCE_SCHEMA,
            "result": "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE",
            "asset_id": self.asset,
            "host_source_sha256": self.host_sha,
            "sequence_id": "lid-latch-open-hold-close-001",
            "sequence_digest": self.sequence_digest,
            "sample_rate_hz": 40,
            "duration_s": 2.5,
            "samples": samples,
        }
        self.rig = {
            "schema": mod.RIG_EVIDENCE_SCHEMA,
            "result": "PASS_SOURCE_OWNED_FRONT_LATCH_RIG_CAPTURE_ENVELOPE_REBIND",
            "asset_id": self.asset,
            "host_source_sha256": self.host_sha,
            "source_mechanical_authority_head": self.source_head,
            "source_capture_result": "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_TO_CLEARANCE_ENVELOPE",
            "source_capture_transition_deg": 9.264790333551197,
            "z_aabb_only_transition_deg": 48.66480246428277,
            "historical_interface_threshold_reclassified_as": "Z_AABB_BROAD_PHASE_ONLY_NOT_CAPTURE_THRESHOLD",
            "motion_envelope_retuned": False,
            "animation_timing_or_playback_accepted": False,
        }
        self.binding = {
            "schema": mod.RIG_BINDING_SCHEMA,
            "asset_id": self.asset,
            "host_source_sha256": self.host_sha,
        }
        self.policy = {
            "schema": mod.CAPTURE_POLICY_SCHEMA,
            "asset_id": self.asset,
            "host_source_sha256": self.host_sha,
            "source_semantics": {
                "z_aabb_transition": "BROAD_PHASE_AXIS_SEPARATION_ONLY_NOT_CAPTURE_THRESHOLD",
            },
            "authority": {
                "animation_timing_owned": False,
                "runtime_controller_owned": False,
            },
        }

    def verify(self, sequence=None, rig=None, contract=None):
        return mod.verify(
            contract or self.contract,
            sequence or self.sequence,
            rig or self.rig,
            self.binding,
            self.policy,
            current_rig_head=self.rig_head,
            source_authority_head=self.source_head,
            rig_binding_blob_sha=self.binding_blob,
            capture_policy_blob_sha=self.policy_blob,
            exact_head="animation-head",
        )

    def test_rebind_characterizes_true_capture_before_broad_phase_without_retime(self) -> None:
        receipt = self.verify()
        self.assertEqual(receipt["result"], mod.RESULT)
        release = receipt["release_timeline"]
        self.assertLess(release["proof_volume_contact_to_separation_crossing_time_s"], release["z_aabb_broad_phase_crossing_time_s"])
        self.assertLess(release["z_aabb_broad_phase_crossing_time_s"], 0.25)
        self.assertEqual(receipt["motion_preservation"]["maximum_latch_curve_formula_residual_deg"], 0.0)
        self.assertFalse(receipt["runtime_controller_accepted"])
        self.assertFalse(receipt["gameplay_accepted"])

    def test_fails_closed_on_historical_z_aabb_capture_relabel(self) -> None:
        bad = copy.deepcopy(self.rig)
        bad["historical_interface_threshold_reclassified_as"] = "CAPTURE_THRESHOLD"
        with self.assertRaisesRegex(AssertionError, "relabeled as capture"):
            self.verify(rig=bad)

    def test_fails_closed_on_motion_key_drift(self) -> None:
        bad = copy.deepcopy(self.sequence)
        bad["samples"][3]["latch_lever_angle_deg"] += 0.25
        with self.assertRaisesRegex(AssertionError, "authored latch curve changed"):
            self.verify(sequence=bad)

    def test_fails_closed_on_runtime_authority_inflation(self) -> None:
        bad = copy.deepcopy(self.contract)
        bad["truth_boundary"]["runtime_controller_accepted"] = True
        with self.assertRaisesRegex(AssertionError, "authority inflation"):
            self.verify(contract=bad)


if __name__ == "__main__":
    unittest.main()
