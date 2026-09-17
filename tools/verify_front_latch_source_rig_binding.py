from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_modular_case import build
import verify_front_latch_pivot_interface as source_interface

SCHEMA = "axm.object-front-latch-source-rig-binding/v0.2"
RESULT = "PASS_SOURCE_OWNED_FRONT_LATCH_RIG_CAPTURE_ENVELOPE_REBIND"
EXPECTED_SOURCE_AUTHORITY_HEAD = "56aaaecb45b520fdff9e08fe2d4ea42562f5690f"
EXPECTED_INTERFACE_SHA256 = "bcbbe098371eb702bc9289a97370744093105925202eda6036bdced6e25e34d3"
EXPECTED_CAPTURE_POLICY_BLOB_SHA = "b96df9c5469dffb20e674edd4b176941eda81b8e"
EXPECTED_CAPTURE_RESULT = "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_TO_CLEARANCE_ENVELOPE"
EXPECTED_HISTORICAL_RIG_HEAD = "3b667ff5d30c46ec2fe7da7679518970f8610018"
EXPECTED_HISTORICAL_PLAN_SHA256 = "81c27ab7b73ed9a43cb3f554b56c3f4294b893712075e33d13f5b02e008455db"
EXPECTED_PRIOR_BINDING_HEAD = "a1acd2bcb2074f41e536562f2673508e2cb0a4d5"
TOL = 1e-12


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    payload = f"blob {len(data)}\0".encode("ascii") + data
    return hashlib.sha1(payload).hexdigest()


def _component_map(host: dict) -> dict[str, dict]:
    return {row["name"]: row for row in build(host)["components"]}


def _corners(component: dict) -> list[tuple[float, float, float]]:
    bounds = source_interface._bounds(component)
    return [
        (x, y, z)
        for x in bounds[0]
        for y in bounds[1]
        for z in bounds[2]
    ]


def _rotate_x(
    point: tuple[float, float, float],
    pivot: tuple[float, float, float],
    angle_deg: float,
) -> tuple[float, float, float]:
    angle = math.radians(angle_deg)
    ca, sa = math.cos(angle), math.sin(angle)
    x, y, z = point
    px, py, pz = pivot
    dy, dz = y - py, z - pz
    return (x, py + dy * ca - dz * sa, pz + dy * sa + dz * ca)


def _bounds_from_points(points: list[tuple[float, float, float]]):
    return tuple((min(p[i] for p in points), max(p[i] for p in points)) for i in range(3))


def _pairwise(points: list[tuple[float, float, float]]) -> list[float]:
    out = []
    for idx, a in enumerate(points):
        for b in points[idx + 1 :]:
            out.append(math.dist(a, b))
    return out


def _max_delta(a: list[float], b: list[float]) -> float:
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


def _axis_overlap(a, b):
    return tuple(min(a[i][1], b[i][1]) - max(a[i][0], b[i][0]) for i in range(3))


def _in_bracket(value: float, bracket: list[float]) -> bool:
    return len(bracket) == 2 and float(bracket[0]) < value < float(bracket[1])


def verify(
    host: dict,
    ownership: dict,
    interface: dict,
    historical_plan: dict,
    capture_policy: dict,
    capture_receipt: dict,
    binding: dict,
    *,
    host_sha: str,
    ownership_sha: str,
    interface_sha: str,
    historical_plan_sha: str,
    capture_policy_blob_sha: str,
    binding_sha: str,
) -> dict:
    if binding.get("schema") != SCHEMA:
        raise AssertionError("unsupported source-rig binding schema")
    if binding.get("asset_id") != host.get("asset_id"):
        raise AssertionError("binding asset identity mismatch")
    if binding.get("host_source_sha256") != host_sha:
        raise AssertionError("binding host source identity mismatch")

    authority = binding.get("source_mechanical_authority", {})
    if authority.get("head") != EXPECTED_SOURCE_AUTHORITY_HEAD:
        raise AssertionError("source mechanical authority head drift")
    if authority.get("role") != "CURRENT_SOURCE_PIVOT_AND_PROOF_VOLUME_CAPTURE_AUTHORITY":
        raise AssertionError("source mechanical authority role drift")

    pivot_ref = authority.get("pivot_interface", {})
    if pivot_ref.get("sha256") != EXPECTED_INTERFACE_SHA256 or interface_sha != EXPECTED_INTERFACE_SHA256:
        raise AssertionError("source pivot interface identity drift")

    capture_ref = authority.get("capture_envelope", {})
    if capture_ref.get("git_blob_sha") != EXPECTED_CAPTURE_POLICY_BLOB_SHA:
        raise AssertionError("declared capture-envelope blob identity drift")
    if capture_policy_blob_sha != EXPECTED_CAPTURE_POLICY_BLOB_SHA:
        raise AssertionError("materialized capture-envelope blob identity drift")
    if capture_ref.get("required_result") != EXPECTED_CAPTURE_RESULT:
        raise AssertionError("declared capture-envelope result drift")

    historical_ref = binding.get("historical_rigging_observation", {})
    if historical_ref.get("head") != EXPECTED_HISTORICAL_RIG_HEAD:
        raise AssertionError("historical Rigging head drift")
    if historical_ref.get("plan_sha256") != EXPECTED_HISTORICAL_PLAN_SHA256 or historical_plan_sha != EXPECTED_HISTORICAL_PLAN_SHA256:
        raise AssertionError("historical Rigging plan identity drift")
    if historical_ref.get("role") != "PROVENANCE_ONLY_NOT_CURRENT_INTERFACE_AUTHORITY":
        raise AssertionError("historical Rigging role drift")

    prior_ref = binding.get("prior_rigging_binding", {})
    if prior_ref.get("head") != EXPECTED_PRIOR_BINDING_HEAD:
        raise AssertionError("prior Rigging binding head drift")
    if prior_ref.get("role") != "HISTORICAL_PRE_CAPTURE_ENVELOPE_CLASSIFICATION":
        raise AssertionError("prior Rigging binding role drift")

    interface_receipt = source_interface.verify(
        host,
        ownership,
        interface,
        historical_plan,
        host_sha=host_sha,
        ownership_sha=ownership_sha,
        interface_sha=interface_sha,
        rigging_plan_sha=historical_plan_sha,
    )
    if interface_receipt.get("result") != source_interface.RESULT:
        raise AssertionError("source-owned pivot interface prerequisite did not pass")

    if capture_policy.get("schema") != "axm.object-front-latch-capture-envelope/v0.1":
        raise AssertionError("capture-envelope policy schema drift")
    if capture_policy.get("asset_id") != host.get("asset_id"):
        raise AssertionError("capture-envelope asset identity mismatch")
    if capture_policy.get("host_source_sha256") != host_sha:
        raise AssertionError("capture-envelope host identity drift")
    policy_pivot = capture_policy.get("pivot_interface", {})
    if policy_pivot.get("sha256") != EXPECTED_INTERFACE_SHA256:
        raise AssertionError("capture-envelope pivot identity drift")
    contact = capture_policy.get("contact_model", {})
    if contact.get("intersection_method") != "POSITIVE_X_INTERVAL_OVERLAP_PLUS_EXACT_YZ_ORIENTED_RECTANGLE_SAT":
        raise AssertionError("capture-envelope contact model drift")
    source_semantics = capture_policy.get("source_semantics", {})
    if source_semantics.get("z_aabb_transition") != "BROAD_PHASE_AXIS_SEPARATION_ONLY_NOT_CAPTURE_THRESHOLD":
        raise AssertionError("capture-envelope broad-phase semantics drift")
    source_authority = capture_policy.get("authority", {})
    if not source_authority.get("hard_surface_owns_source_contact_intent", False):
        raise AssertionError("source contact authority missing")
    if not source_authority.get("hard_surface_owns_proof_volume_capture_envelope", False):
        raise AssertionError("source capture-envelope authority missing")
    forbidden_source_authority = (
        "animation_timing_owned",
        "rigging_motion_authorship_owned",
        "runtime_controller_owned",
        "physics_owned",
        "physical_latch_retention_owned",
        "manufacturing_fit_owned",
    )
    if any(source_authority.get(key, False) for key in forbidden_source_authority):
        raise AssertionError("source capture-envelope authority inflation")

    if capture_receipt.get("result") != EXPECTED_CAPTURE_RESULT:
        raise AssertionError("source capture-envelope receipt did not pass")
    if capture_receipt.get("host_source_sha256") != host_sha:
        raise AssertionError("capture receipt host identity drift")
    if capture_receipt.get("pivot_interface_sha256") != interface_sha:
        raise AssertionError("capture receipt pivot identity drift")
    if capture_receipt.get("contact_model") != contact.get("intersection_method"):
        raise AssertionError("capture receipt contact model drift")
    receipt_truth = capture_receipt.get("truth_boundary", {})
    if receipt_truth.get("z_aabb_only_is_not_capture_threshold") is not True:
        raise AssertionError("capture receipt lost broad-phase distinction")
    if receipt_truth.get("sampled_release_path_reentry_observed") is not False:
        raise AssertionError("capture receipt reports sampled release-path contact reentry")
    for key in (
        "physical_latch_capture_or_retention_proven",
        "manufacturing_fit_or_tolerance_proven",
        "dynamic_release_or_reengagement_forces_proven",
        "continuous_full_assembly_collision_freedom_proven",
        "animation_timing_owned",
        "runtime_controller_owned",
        "physics_owned",
    ):
        if receipt_truth.get(key) is not False:
            raise AssertionError(f"capture receipt truth boundary drift: {key}")

    capture_transition = float(capture_receipt.get("capture_transition_deg"))
    z_aabb_transition = float(capture_receipt.get("z_aabb_only_transition_deg"))
    threshold_gap = float(capture_receipt.get("z_aabb_minus_capture_transition_deg"))
    if not _in_bracket(capture_transition, [9.2647, 9.2649]):
        raise AssertionError("source capture transition drift")
    if not _in_bracket(z_aabb_transition, [48.6647, 48.6649]):
        raise AssertionError("source Z-AABB broad-phase transition drift")
    if threshold_gap + TOL < float(binding.get("required_minimum_threshold_separation_deg", 0.0)):
        raise AssertionError("capture and Z-AABB thresholds insufficiently separated")
    if abs((z_aabb_transition - capture_transition) - threshold_gap) > 1e-10:
        raise AssertionError("capture receipt threshold gap inconsistency")
    if abs(float(interface_receipt["release_threshold_deg"]) - z_aabb_transition) > 1e-10:
        raise AssertionError("historical source-interface threshold is not the retained Z-AABB broad-phase threshold")
    if abs(z_aabb_transition - capture_transition) < 1.0:
        raise AssertionError("source capture and Z-AABB broad-phase thresholds collapsed")

    if binding.get("joint_axis") != interface.get("joint_axis") or binding.get("joint_axis") != [1.0, 0.0, 0.0]:
        raise AssertionError("binding joint axis drift")
    poses = [float(value) for value in binding.get("pose_samples_deg", [])]
    expected_poses = [0.0, 9.25, 9.30, 25.0, 48.65, 48.70, 50.0]
    if poses != expected_poses:
        raise AssertionError("representative pose schedule drift")
    if not _in_bracket(capture_transition, [poses[1], poses[2]]):
        raise AssertionError("representative poses do not bracket source capture transition")
    if not _in_bracket(z_aabb_transition, [poses[4], poses[5]]):
        raise AssertionError("representative poses do not bracket Z-AABB broad-phase transition")

    declared_capture_bracket = [float(v) for v in binding.get("required_capture_transition_bracket_deg", [])]
    declared_z_bracket = [float(v) for v in binding.get("required_z_aabb_only_transition_bracket_deg", [])]
    if declared_capture_bracket != [9.25, 9.30] or not _in_bracket(capture_transition, declared_capture_bracket):
        raise AssertionError("declared capture-transition bracket drift")
    if declared_z_bracket != [48.65, 48.70] or not _in_bracket(z_aabb_transition, declared_z_bracket):
        raise AssertionError("declared Z-AABB transition bracket drift")
    capture_semantics = binding.get("capture_semantics", {})
    if capture_semantics.get("z_aabb_transition") != "BROAD_PHASE_AXIS_SEPARATION_ONLY_NOT_CAPTURE_THRESHOLD":
        raise AssertionError("Rigging broad-phase semantics drift")

    components = _component_map(host)
    rows = []
    max_rigidity_drift = 0.0
    max_pivot_drift = 0.0
    station_pose_z_overlaps: list[list[float]] = []

    for station in interface.get("stations", []):
        lever = components.get(station.get("lever_component"))
        keeper = components.get(station.get("keeper_component"))
        if lever is None or keeper is None:
            raise AssertionError("source-owned latch component missing")
        if station.get("lever_owner_component") != "front_service_panel" or station.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("source-owned latch owner drift")

        pivot = tuple(float(v) for v in station.get("pivot_origin_m", []))
        if len(pivot) != 3:
            raise AssertionError("source-owned pivot missing")
        neutral = _corners(lever)
        neutral_pairwise = _pairwise(neutral)
        keeper_bounds = source_interface._bounds(keeper)
        pose_rows = []
        z_overlaps = []

        for angle in poses:
            moved = [_rotate_x(point, pivot, angle) for point in neutral]
            moved_bounds = _bounds_from_points(moved)
            overlap = _axis_overlap(moved_bounds, keeper_bounds)
            rigid_drift = _max_delta(neutral_pairwise, _pairwise(moved))
            rotated_pivot = _rotate_x(pivot, pivot, angle)
            pivot_drift = math.dist(pivot, rotated_pivot)
            max_rigidity_drift = max(max_rigidity_drift, rigid_drift)
            max_pivot_drift = max(max_pivot_drift, pivot_drift)
            z_overlaps.append(float(overlap[2]))
            pose_rows.append({
                "angle_deg": angle,
                "relative_to_source_capture_transition": "BEFORE_OR_AT_CAPTURE_BOUNDARY" if angle <= capture_transition else "AFTER_CAPTURE_BOUNDARY",
                "relative_to_z_aabb_transition": "BEFORE_OR_AT_Z_AABB_BOUNDARY" if angle <= z_aabb_transition else "AFTER_Z_AABB_BOUNDARY",
                "keeper_axis_overlap_m": {"x": overlap[0], "y": overlap[1], "z": overlap[2]},
                "maximum_rigid_pairwise_distance_drift_m": rigid_drift,
                "pivot_drift_m": pivot_drift,
            })

        if min(pose_rows[0]["keeper_axis_overlap_m"].values()) <= 0.0:
            raise AssertionError("neutral keeper/lever overlap boundary failed")
        if pose_rows[1]["keeper_axis_overlap_m"]["z"] <= 0.0:
            raise AssertionError("9.25 degree Z overlap unexpectedly lost")
        if pose_rows[2]["keeper_axis_overlap_m"]["z"] <= 0.0:
            raise AssertionError("9.30 degree Z overlap unexpectedly lost; cannot demonstrate SAT-vs-Z distinction")
        if pose_rows[4]["keeper_axis_overlap_m"]["z"] <= 0.0:
            raise AssertionError("48.65 degree Z overlap unexpectedly lost")
        if pose_rows[5]["keeper_axis_overlap_m"]["z"] >= 0.0:
            raise AssertionError("48.70 degree Z separation not observed")

        required_release = float(binding.get("required_release_endpoint_keeper_z_separation_m", -1.0))
        endpoint_separation = -float(pose_rows[-1]["keeper_axis_overlap_m"]["z"])
        if endpoint_separation + TOL < required_release:
            raise AssertionError("release endpoint keeper Z separation boundary failed")
        if abs(endpoint_separation - float(capture_receipt["review_release_z_axis_separation_m"])) > 1e-10:
            raise AssertionError("Rigging endpoint separation disagrees with source capture receipt")

        rows.append({
            "station_id": station["id"],
            "pivot_origin_m": list(pivot),
            "lever_component": station["lever_component"],
            "keeper_component": station["keeper_component"],
            "pose_results": pose_rows,
            "source_capture_transition_deg": capture_transition,
            "z_aabb_only_transition_deg": z_aabb_transition,
            "endpoint_keeper_z_separation_m": endpoint_separation,
        })
        station_pose_z_overlaps.append(z_overlaps)

    if len(rows) != 2:
        raise AssertionError("exact bilateral latch station count drift")
    if max_rigidity_drift > TOL or max_pivot_drift > TOL:
        raise AssertionError("rigid lever or fixed pivot drift exceeded tolerance")

    max_bilateral_pose_z_residual = max(
        abs(a - b) for a, b in zip(station_pose_z_overlaps[0], station_pose_z_overlaps[1])
    )
    if max_bilateral_pose_z_residual > TOL:
        raise AssertionError("bilateral representative Z-boundary drift")

    return {
        "schema": "axm.object-front-latch-source-rig-binding-evidence/v0.2",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "host_source_sha256": host_sha,
        "ownership_contract_sha256": ownership_sha,
        "source_mechanical_authority_head": authority["head"],
        "source_pivot_interface_sha256": interface_sha,
        "source_capture_policy_git_blob_sha": capture_policy_blob_sha,
        "source_capture_result": capture_receipt["result"],
        "historical_rigging_observation_head": historical_ref["head"],
        "historical_rigging_observation_plan_sha256": historical_plan_sha,
        "historical_rigging_role": historical_ref["role"],
        "prior_rigging_binding_head": prior_ref["head"],
        "prior_rigging_binding_role": prior_ref["role"],
        "binding_sha256": binding_sha,
        "pose_samples_deg": poses,
        "station_results": rows,
        "maximum_rigid_pairwise_distance_drift_m": max_rigidity_drift,
        "maximum_pivot_drift_m": max_pivot_drift,
        "maximum_bilateral_pose_z_overlap_residual_m": max_bilateral_pose_z_residual,
        "source_capture_transition_deg": capture_transition,
        "source_capture_transition_sample_bracket_deg": capture_receipt["station_results"][0]["capture_transition_sample_bracket_deg"],
        "z_aabb_only_transition_deg": z_aabb_transition,
        "z_aabb_minus_capture_transition_deg": threshold_gap,
        "historical_interface_threshold_reclassified_as": "Z_AABB_BROAD_PHASE_ONLY_NOT_CAPTURE_THRESHOLD",
        "historical_interface_threshold_deg": float(interface_receipt["release_threshold_deg"]),
        "minimum_endpoint_keeper_z_separation_m": min(row["endpoint_keeper_z_separation_m"] for row in rows),
        "host_geometry_changed": False,
        "rig_pivots_changed": False,
        "lever_geometry_changed": False,
        "motion_envelope_retuned": False,
        "animation_timing_or_playback_accepted": False,
        "runtime_controller_or_device_accepted": False,
        "physical_latch_retention_or_forces_proven": False,
        "continuous_full_assembly_collision_freedom_proven": False,
        "truth_boundary": binding["truth_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--ownership", type=Path, required=True)
    parser.add_argument("--interface", type=Path, required=True)
    parser.add_argument("--historical-plan", type=Path, required=True)
    parser.add_argument("--capture-policy", type=Path, required=True)
    parser.add_argument("--capture-receipt", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    host = json.loads(args.host.read_text(encoding="utf-8"))
    ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    interface = json.loads(args.interface.read_text(encoding="utf-8"))
    historical_plan = json.loads(args.historical_plan.read_text(encoding="utf-8"))
    capture_policy = json.loads(args.capture_policy.read_text(encoding="utf-8"))
    capture_receipt = json.loads(args.capture_receipt.read_text(encoding="utf-8"))
    binding = json.loads(args.binding.read_text(encoding="utf-8"))

    receipt = verify(
        host,
        ownership,
        interface,
        historical_plan,
        capture_policy,
        capture_receipt,
        binding,
        host_sha=sha256(args.host),
        ownership_sha=sha256(args.ownership),
        interface_sha=sha256(args.interface),
        historical_plan_sha=sha256(args.historical_plan),
        capture_policy_blob_sha=git_blob_sha(args.capture_policy),
        binding_sha=sha256(args.binding),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "front-latch-source-rig-binding-evidence.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
