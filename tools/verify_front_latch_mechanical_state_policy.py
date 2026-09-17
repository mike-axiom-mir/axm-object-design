from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

POLICY_SCHEMA = "axm.object-front-latch-mechanical-state-policy/v0.1"
INTERFACE_SCHEMA = "axm.object-front-latch-pivot-interface/v0.1"
ANIMATION_GUARD_SCHEMA = "axm.object-animation-mechanical-phase-guard/v0.1"
RESULT = "PASS_SOURCE_OWNED_FRONT_LATCH_MECHANICAL_STATE_GUARD"
EPS = 1e-12


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _close(a: Any, b: Any, eps: float = EPS) -> bool:
    return abs(float(a) - float(b)) <= eps


def verify(
    interface: dict[str, Any],
    animation_guard: dict[str, Any],
    policy: dict[str, Any],
    *,
    interface_sha256: str,
    animation_guard_sha256: str,
    observed_interface_head: str,
    observed_animation_head: str,
) -> dict[str, Any]:
    _require(interface.get("schema") == INTERFACE_SCHEMA, "SOURCE_INTERFACE_SCHEMA_DRIFT")
    _require(animation_guard.get("schema") == ANIMATION_GUARD_SCHEMA, "ANIMATION_GUARD_SCHEMA_DRIFT")
    _require(policy.get("schema") == POLICY_SCHEMA, "MECHANICAL_STATE_POLICY_SCHEMA_DRIFT")
    _require(interface.get("asset_id") == policy.get("asset_id"), "ASSET_IDENTITY_DRIFT")
    _require(animation_guard.get("asset_id") == policy.get("asset_id"), "ANIMATION_ASSET_IDENTITY_DRIFT")

    interface_dep = policy.get("source_interface_dependency", {})
    _require(interface_dep.get("interface_id") == interface.get("interface_id"), "SOURCE_INTERFACE_IDENTITY_DRIFT")
    _require(interface_dep.get("file_sha256") == interface_sha256, "SOURCE_INTERFACE_BYTES_DRIFT")
    _require(interface_dep.get("exact_head") == observed_interface_head, "SOURCE_INTERFACE_HEAD_DRIFT")

    animation_dep = policy.get("animation_observation_dependency", {})
    _require(animation_dep.get("contract_id") == animation_guard.get("contract_id"), "ANIMATION_GUARD_IDENTITY_DRIFT")
    _require(animation_dep.get("file_sha256") == animation_guard_sha256, "ANIMATION_GUARD_BYTES_DRIFT")
    _require(animation_dep.get("exact_head") == observed_animation_head, "ANIMATION_GUARD_HEAD_DRIFT")

    rigging = animation_guard.get("rigging_dependency", {})
    _require(rigging.get("exact_head") == animation_dep.get("required_rigging_head"), "RIGGING_HEAD_DRIFT")
    _require(rigging.get("artifact_id") == animation_dep.get("required_rigging_artifact_id"), "RIGGING_ARTIFACT_ID_DRIFT")
    _require(rigging.get("artifact_sha256") == animation_dep.get("required_rigging_artifact_sha256"), "RIGGING_ARTIFACT_DIGEST_DRIFT")

    travel = interface.get("travel_envelope_deg", {})
    closed_angle = float(travel.get("closed"))
    release_angle = float(travel.get("review_release"))
    minimum_release_separation = float(travel.get("minimum_release_separation_m"))
    _require(_close(closed_angle, 0.0), "SOURCE_CLOSED_ANGLE_DRIFT")
    _require(release_angle > closed_angle, "SOURCE_RELEASE_ANGLE_NOT_POSITIVE")
    _require(minimum_release_separation > 0.0, "SOURCE_RELEASE_SEPARATION_NOT_POSITIVE")

    required_latch = float(rigging.get("required_latch_angle_deg"))
    lid_interval = [float(v) for v in rigging.get("required_lid_open_interval_deg", [])]
    continuous_lower_bound = float(rigging.get("minimum_continuous_separation_lower_bound_m"))
    _require(_close(required_latch, release_angle), "DOWNSTREAM_RELEASE_ANGLE_DRIFT_FROM_SOURCE")
    _require(lid_interval == [0.0, 100.0], "DOWNSTREAM_LID_INTERVAL_DRIFT")
    _require(continuous_lower_bound + EPS >= minimum_release_separation, "DOWNSTREAM_CLEARANCE_BELOW_SOURCE_MINIMUM")

    animation_truth = animation_guard.get("truth_boundary", {})
    _require(animation_truth.get("continuous_moving_lid_keeper_lever_clearance_may_be_composed") is True, "MOVING_LID_CLEARANCE_DEPENDENCY_NOT_GREEN")
    _require(animation_truth.get("continuous_latch_release_clearance_proven") is False, "FALSE_RELEASE_CLEARANCE_PROMOTION")
    _require(animation_truth.get("continuous_latch_reengagement_clearance_proven") is False, "FALSE_REENGAGEMENT_CLEARANCE_PROMOTION")
    _require(animation_truth.get("physical_latch_capture_or_retention_proven") is False, "PHYSICAL_LATCH_AUTHORITY_INFLATION")
    _require(animation_truth.get("runtime_controller_accepted") is False, "RUNTIME_AUTHORITY_INFLATION")
    _require(animation_truth.get("gameplay_accepted") is False, "GAMEPLAY_AUTHORITY_INFLATION")

    states = policy.get("mechanical_states", [])
    expected_ids = ["engaged_neutral", "released_neutral", "released_lid_motion", "reengagement_neutral"]
    _require([state.get("id") for state in states] == expected_ids, "MECHANICAL_STATE_IDENTITY_DRIFT")
    engaged, released, moving, reengage = states

    _require(_close(engaged.get("lid_open_angle_deg"), closed_angle), "ENGAGED_LID_NOT_NEUTRAL")
    _require(_close(engaged.get("latch_lever_angle_deg"), closed_angle), "ENGAGED_LATCH_NOT_CLOSED")
    _require(engaged.get("lid_motion_allowed") is False, "UNRELEASED_LID_MOTION_ALLOWED")
    _require(engaged.get("contact_semantic") == "INTENTIONAL_ENGAGEMENT_OVERLAP", "ENGAGEMENT_SEMANTIC_LOSS")

    _require(_close(released.get("lid_open_angle_deg"), 0.0), "RELEASED_READY_LID_NOT_NEUTRAL")
    _require(_close(released.get("latch_lever_angle_deg"), release_angle), "RELEASED_READY_ANGLE_DRIFT")
    _require(released.get("lid_motion_allowed") is True, "RELEASED_READY_LID_MOTION_FORBIDDEN")
    _require(released.get("contact_semantic") == "SOURCE_REVIEW_RELEASE_ENDPOINT_SEPARATED", "RELEASED_CONTACT_SEMANTIC_DRIFT")

    _require([float(v) for v in moving.get("lid_open_interval_deg", [])] == lid_interval, "MOVING_LID_INTERVAL_DRIFT")
    _require(_close(moving.get("latch_lever_angle_deg"), release_angle), "MOVING_LID_NOT_FULLY_RELEASED")
    _require(moving.get("lid_motion_allowed") is True, "MOVING_LID_STATE_DISABLED")
    _require(moving.get("continuous_clearance_dependency_required") is True, "MOVING_LID_CLEARANCE_DEPENDENCY_DROPPED")
    _require(moving.get("contact_semantic") == "CLEARANCE_REQUIRED_DURING_LID_MOTION", "MOVING_CONTACT_SEMANTIC_DRIFT")

    _require(_close(reengage.get("lid_open_angle_deg"), 0.0), "REENGAGEMENT_LID_NOT_NEUTRAL")
    transition = [float(v) for v in reengage.get("latch_transition_deg", [])]
    _require(transition == [release_angle, closed_angle], "REENGAGEMENT_TRANSITION_DRIFT")
    _require(reengage.get("lid_motion_allowed") is False, "LID_MOTION_ALLOWED_DURING_REENGAGEMENT")
    _require(reengage.get("continuous_clearance_claimed") is False, "FALSE_REENGAGEMENT_CLEARANCE_PROMOTION")
    _require(reengage.get("contact_semantic") == "INTENTIONAL_RETURN_TO_ENGAGEMENT", "REENGAGEMENT_SEMANTIC_DRIFT")

    expected_order = [
        "engaged_neutral",
        "released_neutral",
        "released_lid_motion",
        "released_neutral",
        "reengagement_neutral",
        "engaged_neutral",
    ]
    _require(policy.get("allowed_transition_order") == expected_order, "MECHANICAL_TRANSITION_ORDER_DRIFT")

    rules = policy.get("source_rules", {})
    _require(_close(rules.get("lid_departure_requires_latch_angle_deg"), release_angle), "SOURCE_LID_DEPARTURE_GUARD_DRIFT")
    _require(_close(rules.get("latch_may_enter_below_release_angle_only_when_lid_open_angle_deg"), 0.0), "SOURCE_REENGAGEMENT_NEUTRAL_GUARD_DRIFT")
    _require(rules.get("neutral_engagement_overlap_is_not_a_collision_defect") is True, "ENGAGEMENT_OVERLAP_RELABELED_AS_DEFECT")
    _require(rules.get("continuous_release_clearance_claimed") is False, "FALSE_RELEASE_CLEARANCE_PROMOTION")
    _require(rules.get("continuous_reengagement_clearance_claimed") is False, "FALSE_REENGAGEMENT_CLEARANCE_PROMOTION")
    _require(rules.get("animation_timing_owned") is False, "ANIMATION_AUTHORITY_INFLATION")
    _require(rules.get("runtime_controller_owned") is False, "RUNTIME_AUTHORITY_INFLATION")
    _require(rules.get("physics_engine_accepted") is False, "PHYSICS_AUTHORITY_INFLATION")

    return {
        "schema": "axm.object-front-latch-mechanical-state-policy-evidence/v0.1",
        "result": RESULT,
        "asset_id": policy.get("asset_id"),
        "policy_id": policy.get("policy_id"),
        "source_interface": {
            "head": observed_interface_head,
            "sha256": interface_sha256,
            "closed_angle_deg": closed_angle,
            "review_release_angle_deg": release_angle,
            "minimum_release_separation_m": minimum_release_separation,
        },
        "downstream_observation": {
            "animation_head": observed_animation_head,
            "animation_guard_sha256": animation_guard_sha256,
            "rigging_head": rigging.get("exact_head"),
            "rigging_artifact_id": rigging.get("artifact_id"),
            "rigging_artifact_sha256": rigging.get("artifact_sha256"),
            "moving_lid_interval_deg": lid_interval,
            "required_latch_angle_deg": required_latch,
            "continuous_clearance_lower_bound_m": continuous_lower_bound,
        },
        "mechanical_state_count": len(states),
        "host_geometry_changed": False,
        "animation_motion_authorship_changed": False,
        "truth_boundary": {
            "source_mechanical_admissibility_owned": True,
            "intentional_neutral_engagement_overlap_preserved": True,
            "lid_motion_requires_exact_release_state": True,
            "return_to_neutral_required_before_reengagement": True,
            "continuous_moving_lid_clearance_inherited_only_by_exact_dependency": True,
            "continuous_latch_release_clearance_proven": False,
            "continuous_latch_reengagement_clearance_proven": False,
            "physical_latch_capture_or_retention_proven": False,
            "animation_timing_owned": False,
            "runtime_controller_owned": False,
            "physics_engine_accepted": False,
            "gameplay_accepted": False,
            "canon_or_production_ready": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", type=Path, required=True)
    parser.add_argument("--animation-guard", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--observed-interface-head", required=True)
    parser.add_argument("--observed-animation-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    interface = json.loads(args.interface.read_text(encoding="utf-8"))
    animation_guard = json.loads(args.animation_guard.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    receipt = verify(
        interface,
        animation_guard,
        policy,
        interface_sha256=sha256(args.interface),
        animation_guard_sha256=sha256(args.animation_guard),
        observed_interface_head=args.observed_interface_head,
        observed_animation_head=args.observed_animation_head,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    observation = receipt["downstream_observation"]
    (args.out / "summary.txt").write_text(
        f"{RESULT}\n"
        f"mechanical_state_count={receipt['mechanical_state_count']}\n"
        f"review_release_angle_deg={receipt['source_interface']['review_release_angle_deg']:.18g}\n"
        f"moving_lid_interval_deg={observation['moving_lid_interval_deg']}\n"
        f"continuous_clearance_lower_bound_m={observation['continuous_clearance_lower_bound_m']:.18g}\n"
        f"host_geometry_changed={str(receipt['host_geometry_changed']).lower()}\n"
        f"animation_motion_authorship_changed={str(receipt['animation_motion_authorship_changed']).lower()}\n",
        encoding="utf-8",
    )
    print((args.out / "summary.txt").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
