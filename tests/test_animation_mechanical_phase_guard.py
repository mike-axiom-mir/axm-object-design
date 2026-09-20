from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "verify_animation_mechanical_phase_guard.py"
SPEC = importlib.util.spec_from_file_location("verify_animation_mechanical_phase_guard", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class AnimationMechanicalPhaseGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sequence = {
            "schema": mod.SEQUENCE_SCHEMA,
            "sequence_id": "lid-latch-open-hold-close-001",
            "asset_id": "modular-equipment-case-001",
            "host_source_sha256": "source-sha",
            "sample_rate_hz": 40,
            "duration_s": 2.5,
            "phases": [
                {
                    "id": "release_latches",
                    "start_s": 0.0,
                    "end_s": 0.25,
                    "lid_policy": "HOLD_NEUTRAL",
                    "latch_start_angle_deg": 0.0,
                    "latch_end_angle_deg": 50.0,
                },
                {
                    "id": "play_exact_lid_clip",
                    "start_s": 0.25,
                    "end_s": 2.25,
                    "lid_policy": "COPY_EXACT_AUTHORED_SAMPLES_UNRETIMED",
                    "latch_start_angle_deg": 50.0,
                    "latch_end_angle_deg": 50.0,
                },
                {
                    "id": "reengage_latches",
                    "start_s": 2.25,
                    "end_s": 2.5,
                    "lid_policy": "HOLD_NEUTRAL",
                    "latch_start_angle_deg": 50.0,
                    "latch_end_angle_deg": 0.0,
                },
            ],
            "ordering_contract": {
                "lid_may_move_only_when_latch_angle_deg": 50.0,
                "latch_may_enter_below_rig_separation_threshold_only_when_lid_angle_deg": 0.0,
            },
        }
        digest = mod._canonical_digest(self.sequence)
        self.contract = {
            "schema": mod.CONTRACT_SCHEMA,
            "asset_id": "modular-equipment-case-001",
            "sequence_dependency": {
                "sequence_id": "lid-latch-open-hold-close-001",
                "sequence_digest": digest,
                "required_sample_rate_hz": 40,
                "required_duration_s": 2.5,
                "required_terminal_latch_angle_deg": 50.0,
            },
            "rigging_dependency": {
                "exact_head": "rig-head",
                "artifact_id": 123,
                "artifact_sha256": "artifact-sha",
                "required_result": "PASS_CONTINUOUS_KEEPER_LEVER_CLEARANCE_DURING_LID_MOTION__ENGAGEMENT_OVERLAP_HELD",
                "historical_animation_pose_set_head": "historical-animation-head",
                "required_latch_angle_deg": 50.0,
                "required_lid_open_interval_deg": [0.0, 100.0],
                "minimum_continuous_separation_lower_bound_m": 0.0015,
            },
            "truth_boundary": {
                "motion_authorship_changed": False,
                "continuous_moving_lid_keeper_lever_clearance_may_be_composed": True,
                "continuous_latch_release_clearance_proven": False,
                "continuous_latch_reengagement_clearance_proven": False,
                "runtime_controller_accepted": False,
                "gameplay_accepted": False,
            },
        }
        self.rigging = {
            "schema": mod.RIGGING_SCHEMA,
            "result": self.contract["rigging_dependency"]["required_result"],
            "exact_identity_chain": {
                "animation_sequence_id": "lid-latch-open-hold-close-001",
                "animation_sequence_digest": digest,
                "animation_pose_set_head": "historical-animation-head",
                "host_source_sha256": "source-sha",
            },
            "continuous_clearance": {
                "continuous_lid_motion_interval": {
                    "lid_open_angle_deg": [0.0, 100.0],
                    "latch_lever_angle_deg": 50.0,
                    "minimum_continuous_separation_lower_bound_m": 0.0015,
                }
            },
            "truth_boundary": {
                "continuous_lid_motion_keeper_lever_clearance_proven": True,
                "continuous_latch_release_clearance_proven": False,
                "continuous_latch_reengagement_clearance_proven": False,
                "animation_accepted": False,
                "runtime_accepted": False,
            },
        }
        samples = []
        for index in range(101):
            time_s = index / 40.0
            if index < 10:
                lid = 0.0
                latch = 5.0 * index
            elif index <= 90:
                latch = 50.0
                lid = 0.0 if index in (10, 90) else 100.0
            else:
                lid = 0.0
                latch = 50.0 - 5.0 * (index - 90)
            samples.append(
                {
                    "index": index,
                    "time_s": time_s,
                    "lid_open_angle_deg": lid,
                    "latch_lever_angle_deg": latch,
                }
            )
        self.motion = {
            "sequence_id": "lid-latch-open-hold-close-001",
            "sequence_digest": digest,
            "sample_rate_hz": 40,
            "duration_s": 2.5,
            "endpoint_inclusive_sample_count": 101,
            "samples": samples,
        }

    def test_exact_composition_passes(self) -> None:
        receipt = mod.verify(
            self.contract,
            self.sequence,
            self.motion,
            self.rigging,
            exact_head="animation-head",
            observed_rigging_head="rig-head",
        )
        self.assertEqual(receipt["result"], mod.RESULT)
        self.assertTrue(receipt["composition"]["continuous_moving_lid_phase_guard_proven_by_composition"])
        self.assertFalse(receipt["truth_boundary"]["continuous_latch_release_clearance_proven"])

    def test_hidden_nonreleased_moving_sample_fails_closed(self) -> None:
        motion = copy.deepcopy(self.motion)
        motion["samples"][20]["latch_lever_angle_deg"] = 49.9
        with self.assertRaisesRegex(AssertionError, "MOVING_LID_NOT_FULLY_RELEASED"):
            mod.verify(
                self.contract,
                self.sequence,
                motion,
                self.rigging,
                exact_head="animation-head",
                observed_rigging_head="rig-head",
            )

    def test_latch_transition_requires_neutral_lid_policy(self) -> None:
        sequence = copy.deepcopy(self.sequence)
        sequence["phases"][0]["lid_policy"] = "ALLOW_MOTION"
        contract = copy.deepcopy(self.contract)
        contract["sequence_dependency"]["sequence_digest"] = mod._canonical_digest(sequence)
        motion = copy.deepcopy(self.motion)
        motion["sequence_digest"] = contract["sequence_dependency"]["sequence_digest"]
        rigging = copy.deepcopy(self.rigging)
        rigging["exact_identity_chain"]["animation_sequence_digest"] = contract["sequence_dependency"]["sequence_digest"]
        with self.assertRaisesRegex(AssertionError, "LATCH_TRANSITION_NOT_NEUTRAL_LID"):
            mod.verify(
                contract,
                sequence,
                motion,
                rigging,
                exact_head="animation-head",
                observed_rigging_head="rig-head",
            )

    def test_rigging_release_nonclaim_cannot_be_silently_promoted(self) -> None:
        rigging = copy.deepcopy(self.rigging)
        rigging["truth_boundary"]["continuous_latch_release_clearance_proven"] = True
        with self.assertRaisesRegex(AssertionError, "RIGGING_RELEASE_BOUNDARY_WEAKENED"):
            mod.verify(
                self.contract,
                self.sequence,
                self.motion,
                rigging,
                exact_head="animation-head",
                observed_rigging_head="rig-head",
            )


if __name__ == "__main__":
    unittest.main()
