from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "axm.object-animation-mechanical-phase-guard/v0.1"
SEQUENCE_SCHEMA = "axm.object-lid-latch-motion-sequence/v0.1"
RIGGING_SCHEMA = "axm.object-keeper-lever-continuous-lid-clearance/v0.1"
RESULT = "PASS_CONTINUOUS_MOVING_LID_PHASE_GUARD_OVER_RIGGING_CLEARANCE"
EPS = 1e-12


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _close(a: float, b: float, tolerance: float = EPS) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify(
    contract: dict[str, Any],
    sequence: dict[str, Any],
    motion_evidence: dict[str, Any],
    rigging_receipt: dict[str, Any],
    *,
    exact_head: str,
    observed_rigging_head: str,
) -> dict[str, Any]:
    _require(contract.get("schema") == CONTRACT_SCHEMA, "PHASE_GUARD_CONTRACT_SCHEMA_DRIFT")
    _require(sequence.get("schema") == SEQUENCE_SCHEMA, "SEQUENCE_SCHEMA_DRIFT")
    _require(rigging_receipt.get("schema") == RIGGING_SCHEMA, "RIGGING_RECEIPT_SCHEMA_DRIFT")

    sequence_dep = contract.get("sequence_dependency", {})
    rigging_dep = contract.get("rigging_dependency", {})
    truth = contract.get("truth_boundary", {})

    _require(sequence.get("asset_id") == contract.get("asset_id"), "ASSET_IDENTITY_DRIFT")
    _require(sequence.get("sequence_id") == sequence_dep.get("sequence_id"), "SEQUENCE_IDENTITY_DRIFT")
    sequence_digest = _canonical_digest(sequence)
    _require(sequence_digest == sequence_dep.get("sequence_digest"), "SEQUENCE_DIGEST_DRIFT")
    _require(int(sequence.get("sample_rate_hz")) == int(sequence_dep.get("required_sample_rate_hz")), "SEQUENCE_RATE_DRIFT")
    _require(_close(float(sequence.get("duration_s")), float(sequence_dep.get("required_duration_s"))), "SEQUENCE_DURATION_DRIFT")

    terminal_latch = float(sequence_dep.get("required_terminal_latch_angle_deg"))
    _require(_close(terminal_latch, 50.0), "TERMINAL_LATCH_POLICY_DRIFT")

    _require(observed_rigging_head == rigging_dep.get("exact_head"), "RIGGING_HEAD_DRIFT")
    _require(rigging_receipt.get("result") == rigging_dep.get("required_result"), "RIGGING_CONTINUOUS_CLEARANCE_NOT_GREEN")

    identity = rigging_receipt.get("exact_identity_chain", {})
    _require(identity.get("animation_sequence_id") == sequence.get("sequence_id"), "RIGGING_SEQUENCE_IDENTITY_DRIFT")
    _require(identity.get("animation_sequence_digest") == sequence_digest, "RIGGING_SEQUENCE_DIGEST_DRIFT")
    _require(
        identity.get("animation_pose_set_head") == rigging_dep.get("historical_animation_pose_set_head"),
        "RIGGING_HISTORICAL_ANIMATION_POSE_SET_DRIFT",
    )
    _require(identity.get("host_source_sha256") == sequence.get("host_source_sha256"), "RIGGING_HOST_SOURCE_DRIFT")

    continuous = rigging_receipt.get("continuous_clearance", {}).get("continuous_lid_motion_interval", {})
    required_lid_interval = [float(v) for v in rigging_dep.get("required_lid_open_interval_deg", [])]
    observed_lid_interval = [float(v) for v in continuous.get("lid_open_angle_deg", [])]
    _require(observed_lid_interval == required_lid_interval, "RIGGING_LID_INTERVAL_DRIFT")
    _require(
        _close(float(continuous.get("latch_lever_angle_deg")), float(rigging_dep.get("required_latch_angle_deg"))),
        "RIGGING_RELEASE_ANGLE_DRIFT",
    )
    minimum_clearance = float(continuous.get("minimum_continuous_separation_lower_bound_m"))
    declared_minimum_clearance = float(rigging_dep.get("minimum_continuous_separation_lower_bound_m"))
    _require(minimum_clearance > 0.0, "RIGGING_CONTINUOUS_CLEARANCE_NOT_POSITIVE")
    _require(_close(minimum_clearance, declared_minimum_clearance, 1e-15), "RIGGING_CONTINUOUS_CLEARANCE_VALUE_DRIFT")

    rig_truth = rigging_receipt.get("truth_boundary", {})
    _require(rig_truth.get("continuous_lid_motion_keeper_lever_clearance_proven") is True, "RIGGING_MOVING_LID_CLEARANCE_FLAG_MISSING")
    _require(rig_truth.get("continuous_latch_release_clearance_proven") is False, "RIGGING_RELEASE_BOUNDARY_WEAKENED")
    _require(rig_truth.get("continuous_latch_reengagement_clearance_proven") is False, "RIGGING_REENGAGEMENT_BOUNDARY_WEAKENED")
    _require(rig_truth.get("animation_accepted") is False, "RIGGING_ANIMATION_AUTHORITY_INFLATION")
    _require(rig_truth.get("runtime_accepted") is False, "RIGGING_RUNTIME_AUTHORITY_INFLATION")

    phases = sequence.get("phases", [])
    _require(len(phases) == 3, "PHASE_COUNT_DRIFT")
    _require([row.get("id") for row in phases] == ["release_latches", "play_exact_lid_clip", "reengage_latches"], "PHASE_IDENTITY_DRIFT")
    release, moving, reengage = phases

    _require(_close(release.get("start_s"), 0.0) and _close(release.get("end_s"), 0.25), "RELEASE_PHASE_TIME_DRIFT")
    _require(_close(moving.get("start_s"), 0.25) and _close(moving.get("end_s"), 2.25), "MOVING_PHASE_TIME_DRIFT")
    _require(_close(reengage.get("start_s"), 2.25) and _close(reengage.get("end_s"), 2.5), "REENGAGEMENT_PHASE_TIME_DRIFT")
    _require(release.get("lid_policy") == "HOLD_NEUTRAL", "LATCH_TRANSITION_NOT_NEUTRAL_LID")
    _require(reengage.get("lid_policy") == "HOLD_NEUTRAL", "LATCH_TRANSITION_NOT_NEUTRAL_LID")
    _require(moving.get("lid_policy") == "COPY_EXACT_AUTHORED_SAMPLES_UNRETIMED", "MOVING_PHASE_LID_POLICY_DRIFT")
    _require(_close(release.get("latch_start_angle_deg"), 0.0), "RELEASE_START_ANGLE_DRIFT")
    _require(_close(release.get("latch_end_angle_deg"), terminal_latch), "RELEASE_END_ANGLE_DRIFT")
    _require(_close(moving.get("latch_start_angle_deg"), terminal_latch), "MOVING_PHASE_LATCH_GUARD_DRIFT")
    _require(_close(moving.get("latch_end_angle_deg"), terminal_latch), "MOVING_PHASE_LATCH_GUARD_DRIFT")
    _require(_close(reengage.get("latch_start_angle_deg"), terminal_latch), "REENGAGEMENT_START_ANGLE_DRIFT")
    _require(_close(reengage.get("latch_end_angle_deg"), 0.0), "REENGAGEMENT_END_ANGLE_DRIFT")

    ordering = sequence.get("ordering_contract", {})
    _require(_close(ordering.get("lid_may_move_only_when_latch_angle_deg"), terminal_latch), "ORDERING_CONTRACT_RELEASE_ANGLE_DRIFT")
    _require(
        ordering.get("latch_may_enter_below_rig_separation_threshold_only_when_lid_angle_deg") == 0.0,
        "ORDERING_CONTRACT_NEUTRAL_LID_DRIFT",
    )

    _require(motion_evidence.get("sequence_id") == sequence.get("sequence_id"), "MOTION_EVIDENCE_SEQUENCE_ID_DRIFT")
    _require(motion_evidence.get("sequence_digest") == sequence_digest, "MOTION_EVIDENCE_SEQUENCE_DIGEST_DRIFT")
    _require(int(motion_evidence.get("sample_rate_hz")) == int(sequence.get("sample_rate_hz")), "MOTION_EVIDENCE_RATE_DRIFT")
    _require(_close(float(motion_evidence.get("duration_s")), float(sequence.get("duration_s"))), "MOTION_EVIDENCE_DURATION_DRIFT")

    samples = motion_evidence.get("samples", [])
    _require(len(samples) == 101, "MOTION_EVIDENCE_SAMPLE_COUNT_DRIFT")
    _require(int(motion_evidence.get("endpoint_inclusive_sample_count")) == 101, "MOTION_EVIDENCE_ENDPOINT_COUNT_DRIFT")

    moving_sample_count = 0
    latch_transition_sample_count = 0
    maximum_lid_open = 0.0
    minimum_latch_during_nonneutral_lid = terminal_latch
    maximum_latch_during_nonneutral_lid = terminal_latch

    for row in samples:
        lid_angle = float(row.get("lid_open_angle_deg"))
        latch_angle = float(row.get("latch_lever_angle_deg"))
        time_s = float(row.get("time_s"))
        maximum_lid_open = max(maximum_lid_open, lid_angle)

        if lid_angle > EPS:
            moving_sample_count += 1
            minimum_latch_during_nonneutral_lid = min(minimum_latch_during_nonneutral_lid, latch_angle)
            maximum_latch_during_nonneutral_lid = max(maximum_latch_during_nonneutral_lid, latch_angle)
            _require(_close(latch_angle, terminal_latch), "MOVING_LID_NOT_FULLY_RELEASED")
        elif not _close(latch_angle, terminal_latch):
            latch_transition_sample_count += 1

        if time_s < float(moving.get("start_s")) - EPS or time_s > float(moving.get("end_s")) + EPS:
            _require(lid_angle <= EPS, "LID_MOVED_DURING_LATCH_TRANSITION")

    _require(moving_sample_count > 0, "NO_NONNEUTRAL_LID_MOTION_OBSERVED")
    _require(latch_transition_sample_count > 0, "NO_LATCH_TRANSITION_OBSERVED")
    _require(maximum_lid_open <= required_lid_interval[1] + EPS, "MOTION_EXCEEDS_RIGGING_CONTINUOUS_LID_INTERVAL")
    _require(_close(float(samples[0].get("lid_open_angle_deg")), 0.0), "START_LID_NOT_NEUTRAL")
    _require(_close(float(samples[0].get("latch_lever_angle_deg")), 0.0), "START_LATCH_NOT_ENGAGED")
    _require(_close(float(samples[-1].get("lid_open_angle_deg")), 0.0), "END_LID_NOT_NEUTRAL")
    _require(_close(float(samples[-1].get("latch_lever_angle_deg")), 0.0), "END_LATCH_NOT_ENGAGED")

    _require(truth.get("motion_authorship_changed") is False, "CONTRACT_MOTION_CHANGE_FLAG_DRIFT")
    _require(truth.get("continuous_moving_lid_keeper_lever_clearance_may_be_composed") is True, "CONTRACT_CONTINUOUS_COMPOSITION_FLAG_MISSING")
    _require(truth.get("continuous_latch_release_clearance_proven") is False, "CONTRACT_RELEASE_BOUNDARY_WEAKENED")
    _require(truth.get("continuous_latch_reengagement_clearance_proven") is False, "CONTRACT_REENGAGEMENT_BOUNDARY_WEAKENED")
    _require(truth.get("runtime_controller_accepted") is False, "CONTRACT_RUNTIME_AUTHORITY_INFLATION")
    _require(truth.get("gameplay_accepted") is False, "CONTRACT_GAMEPLAY_AUTHORITY_INFLATION")

    return {
        "schema": "axm.object-animation-mechanical-phase-guard-evidence/v0.1",
        "result": RESULT,
        "exact_animation_head": exact_head,
        "asset_id": sequence.get("asset_id"),
        "sequence_id": sequence.get("sequence_id"),
        "sequence_digest": sequence_digest,
        "motion_authorship_changed": False,
        "rigging_dependency": {
            "exact_head": observed_rigging_head,
            "artifact_id": rigging_dep.get("artifact_id"),
            "artifact_sha256": rigging_dep.get("artifact_sha256"),
            "result": rigging_receipt.get("result"),
            "historical_animation_pose_set_head": identity.get("animation_pose_set_head"),
        },
        "composition": {
            "release_phase_lid_neutral": True,
            "moving_lid_phase_latch_angle_deg": terminal_latch,
            "reengagement_phase_lid_neutral": True,
            "moving_lid_observed_sample_count": moving_sample_count,
            "latch_transition_observed_sample_count": latch_transition_sample_count,
            "maximum_observed_lid_open_angle_deg": maximum_lid_open,
            "minimum_observed_latch_angle_during_nonneutral_lid_deg": minimum_latch_during_nonneutral_lid,
            "maximum_observed_latch_angle_during_nonneutral_lid_deg": maximum_latch_during_nonneutral_lid,
            "rigging_continuous_lid_interval_deg": observed_lid_interval,
            "rigging_continuous_clearance_lower_bound_m": minimum_clearance,
            "continuous_moving_lid_phase_guard_proven_by_composition": True,
        },
        "truth_boundary": {
            "continuous_lid_motion_keeper_lever_clearance_composed": True,
            "continuous_latch_release_clearance_proven": False,
            "continuous_latch_reengagement_clearance_proven": False,
            "engagement_overlap_at_neutral_preserved": True,
            "physical_latch_capture_or_retention_proven": False,
            "target_engine_interpolation_proven_by_this_gate": False,
            "runtime_controller_accepted": False,
            "physics_or_collision_engine_accepted": False,
            "gameplay_accepted": False,
            "final_visual_motion_accepted": False,
            "canon_or_production_ready": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--sequence", type=Path, required=True)
    parser.add_argument("--motion-evidence", type=Path, required=True)
    parser.add_argument("--rigging-receipt", type=Path, required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--observed-rigging-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    receipt = verify(
        json.loads(args.contract.read_text(encoding="utf-8")),
        json.loads(args.sequence.read_text(encoding="utf-8")),
        json.loads(args.motion_evidence.read_text(encoding="utf-8")),
        json.loads(args.rigging_receipt.read_text(encoding="utf-8")),
        exact_head=args.exact_head,
        observed_rigging_head=args.observed_rigging_head,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    composition = receipt["composition"]
    (args.out / "summary.txt").write_text(
        f"{RESULT}\n"
        f"moving_lid_observed_sample_count={composition['moving_lid_observed_sample_count']}\n"
        f"latch_transition_observed_sample_count={composition['latch_transition_observed_sample_count']}\n"
        f"maximum_observed_lid_open_angle_deg={composition['maximum_observed_lid_open_angle_deg']:.18g}\n"
        f"moving_lid_phase_latch_angle_deg={composition['moving_lid_phase_latch_angle_deg']:.18g}\n"
        f"rigging_continuous_clearance_lower_bound_m={composition['rigging_continuous_clearance_lower_bound_m']:.18g}\n",
        encoding="utf-8",
    )
    print((args.out / "summary.txt").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
